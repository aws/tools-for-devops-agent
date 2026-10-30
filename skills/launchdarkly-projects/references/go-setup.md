# Go Project Setup

Implementation patterns for Go applications using the LaunchDarkly API.

## Prerequisites

```bash
go get github.com/joho/godotenv
```

## Basic Project Manager

Create a package for project operations:

```go
// pkg/launchdarkly/projects.go
package launchdarkly

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "os"
)

const BaseURL = "https://app.launchdarkly.com/api/v2"

type ProjectManager struct {
    apiToken string
    client   *http.Client
}

type Project struct {
    Name         string        `json:"name"`
    Key          string        `json:"key"`
    Tags         []string      `json:"tags,omitempty"`
    Environments *Environments `json:"environments,omitempty"`
}

type Environments struct {
    Items []Environment `json:"items"`
}

type Environment struct {
    Name   string `json:"name"`
    Key    string `json:"key"`
    APIKey string `json:"apiKey"`
}

func NewProjectManager(apiToken string) *ProjectManager {
    if apiToken == "" {
        apiToken = os.Getenv("LAUNCHDARKLY_API_TOKEN")
    }
    
    return &ProjectManager{
        apiToken: apiToken,
        client:   &http.Client{},
    }
}

func (pm *ProjectManager) CreateProject(name, key string, tags []string) (*Project, error) {
    payload := map[string]interface{}{
        "name": name,
        "key":  key,
    }
    if tags != nil {
        payload["tags"] = tags
    }
    
    body, err := json.Marshal(payload)
    if err != nil {
        return nil, fmt.Errorf("marshal payload: %w", err)
    }
    
    req, err := http.NewRequest("POST", fmt.Sprintf("%s/projects", BaseURL), bytes.NewReader(body))
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }
    
    req.Header.Set("Authorization", pm.apiToken)
    req.Header.Set("Content-Type", "application/json")
    
    resp, err := pm.client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("do request: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode == http.StatusConflict {
        // Project exists, fetch it
        return pm.GetProject(key)
    }
    
    if resp.StatusCode != http.StatusCreated {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, body)
    }
    
    var project Project
    if err := json.NewDecoder(resp.Body).Decode(&project); err != nil {
        return nil, fmt.Errorf("decode response: %w", err)
    }
    
    return &project, nil
}

func (pm *ProjectManager) GetProject(projectKey string) (*Project, error) {
    req, err := http.NewRequest("GET", fmt.Sprintf("%s/projects/%s?expand=environments", BaseURL, projectKey), nil)
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }
    
    req.Header.Set("Authorization", pm.apiToken)
    
    resp, err := pm.client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("do request: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("project not found: %d", resp.StatusCode)
    }
    
    var project Project
    if err := json.NewDecoder(resp.Body).Decode(&project); err != nil {
        return nil, fmt.Errorf("decode response: %w", err)
    }
    
    return &project, nil
}

func (pm *ProjectManager) GetSDKKey(projectKey, environment string) (string, error) {
    project, err := pm.GetProject(projectKey)
    if err != nil {
        return "", err
    }
    
    if project.Environments == nil {
        return "", fmt.Errorf("no environments found")
    }
    
    for _, env := range project.Environments.Items {
        if env.Key == environment {
            return env.APIKey, nil
        }
    }
    
    return "", fmt.Errorf("environment '%s' not found", environment)
}

func (pm *ProjectManager) ListProjects() ([]Project, error) {
    req, err := http.NewRequest("GET", fmt.Sprintf("%s/projects", BaseURL), nil)
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }
    
    req.Header.Set("Authorization", pm.apiToken)
    
    resp, err := pm.client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("do request: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("failed to list projects: %d", resp.StatusCode)
    }
    
    var result struct {
        Items []Project `json:"items"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("decode response: %w", err)
    }
    
    return result.Items, nil
}
```

## Usage Examples

### Create a Project

```go
package main

import (
    "fmt"
    "log"
    
    "yourmodule/pkg/launchdarkly"
)

func main() {
    pm := launchdarkly.NewProjectManager("")
    
    project, err := pm.CreateProject(
        "Customer Agent Service",
        "customer-ai",
        []string{"ai-configs", "production"},
    )
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("✓ Created project: %s (%s)\n", project.Name, project.Key)
}
```

### Get SDK Key

```go
func main() {
    pm := launchdarkly.NewProjectManager("")
    
    // Get production SDK key
    sdkKey, err := pm.GetSDKKey("customer-ai", "production")
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("Production SDK Key: %s\n", sdkKey)
}
```

### List Projects

```go
func main() {
    pm := launchdarkly.NewProjectManager("")
    
    projects, err := pm.ListProjects()
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Println("Projects:")
    for _, project := range projects {
        fmt.Printf("  - %s (%s)\n", project.Name, project.Key)
    }
}
```

## HTTP Server Integration

Integrate into an HTTP server:

```go
// cmd/server/main.go
package main

import (
    "log"
    "net/http"
    "os"
    
    "yourmodule/pkg/launchdarkly"
)

func main() {
    // Initialize LaunchDarkly project
    pm := launchdarkly.NewProjectManager(os.Getenv("LAUNCHDARKLY_API_TOKEN"))
    
    project, err := pm.CreateProject(
        "Go API Service",
        "go-api-service",
        []string{"api", "ai-configs"},
    )
    if err != nil {
        log.Fatalf("Failed to initialize LaunchDarkly: %v", err)
    }
    
    // Get SDK key
    sdkKey, err := pm.GetSDKKey("go-api-service", "production")
    if err != nil {
        log.Fatalf("Failed to get SDK key: %v", err)
    }
    
    // Store SDK key for SDK initialization
    os.Setenv("LD_SDK_KEY", sdkKey)
    
    log.Printf("✓ LaunchDarkly project ready: %s\n", project.Key)
    
    // Start server
    http.HandleFunc("/health", healthHandler)
    log.Fatal(http.ListenAndServe(":8080", nil))
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    w.Write([]byte("OK"))
}
```

## CLI Tool

Create a CLI for project management:

```go
// cmd/ldprojects/main.go
package main

import (
    "flag"
    "fmt"
    "log"
    "os"
    "strings"
    
    "yourmodule/pkg/launchdarkly"
)

func main() {
    createCmd := flag.NewFlagSet("create", flag.ExitOnError)
    createName := createCmd.String("name", "", "Project name")
    createKey := createCmd.String("key", "", "Project key")
    createTags := createCmd.String("tags", "", "Comma-separated tags")
    
    listCmd := flag.NewFlagSet("list", flag.ExitOnError)
    
    getKeyCmd := flag.NewFlagSet("get-key", flag.ExitOnError)
    getKeyProject := getKeyCmd.String("project", "", "Project key")
    getKeyEnv := getKeyCmd.String("env", "production", "Environment")
    
    if len(os.Args) < 2 {
        fmt.Println("Usage: ldprojects [create|list|get-key] [options]")
        os.Exit(1)
    }
    
    pm := launchdarkly.NewProjectManager("")
    
    switch os.Args[1] {
    case "create":
        createCmd.Parse(os.Args[2:])
        if *createName == "" || *createKey == "" {
            log.Fatal("name and key are required")
        }
        
        var tags []string
        if *createTags != "" {
            tags = strings.Split(*createTags, ",")
        }
        
        project, err := pm.CreateProject(*createName, *createKey, tags)
        if err != nil {
            log.Fatal(err)
        }
        
        fmt.Printf("✓ Created: %s (%s)\n", project.Name, project.Key)
        
    case "list":
        listCmd.Parse(os.Args[2:])
        
        projects, err := pm.ListProjects()
        if err != nil {
            log.Fatal(err)
        }
        
        fmt.Println("Projects:")
        for _, project := range projects {
            fmt.Printf("  - %s (%s)\n", project.Name, project.Key)
        }
        
    case "get-key":
        getKeyCmd.Parse(os.Args[2:])
        if *getKeyProject == "" {
            log.Fatal("project is required")
        }
        
        sdkKey, err := pm.GetSDKKey(*getKeyProject, *getKeyEnv)
        if err != nil {
            log.Fatal(err)
        }
        
        fmt.Println(sdkKey)
        
    default:
        fmt.Println("Unknown command:", os.Args[1])
        os.Exit(1)
    }
}
```

**Usage:**
```bash
go run cmd/ldprojects/main.go create -name "My Agent" -key my-ai -tags ai-configs,production
go run cmd/ldprojects/main.go list
go run cmd/ldprojects/main.go get-key -project my-ai -env production
```

## Error Handling

Add comprehensive error handling:

```go
type LaunchDarklyError struct {
    StatusCode int
    Message    string
}

func (e *LaunchDarklyError) Error() string {
    return fmt.Sprintf("LaunchDarkly API error (%d): %s", e.StatusCode, e.Message)
}

func (pm *ProjectManager) CreateProject(name, key string, tags []string) (*Project, error) {
    // ... request setup ...
    
    resp, err := pm.client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()
    
    switch resp.StatusCode {
    case http.StatusCreated:
        var project Project
        if err := json.NewDecoder(resp.Body).Decode(&project); err != nil {
            return nil, fmt.Errorf("decode response: %w", err)
        }
        return &project, nil
        
    case http.StatusConflict:
        return pm.GetProject(key)
        
    case http.StatusUnauthorized:
        return nil, &LaunchDarklyError{resp.StatusCode, "Invalid API token"}
        
    case http.StatusForbidden:
        return nil, &LaunchDarklyError{resp.StatusCode, "Insufficient permissions (need projects:write)"}
        
    default:
        body, _ := io.ReadAll(resp.Body)
        return nil, &LaunchDarklyError{resp.StatusCode, string(body)}
    }
}
```

## Testing

Mock the HTTP client for testing:

```go
// pkg/launchdarkly/projects_test.go
package launchdarkly

import (
    "net/http"
    "net/http/httptest"
    "testing"
)

func TestCreateProject(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.Method != "POST" {
            t.Errorf("Expected POST, got %s", r.Method)
        }
        
        w.WriteHeader(http.StatusCreated)
        w.Write([]byte(`{"name":"Test","key":"test","tags":[]}`))
    }))
    defer server.Close()
    
    pm := &ProjectManager{
        apiToken: "test-token",
        client:   server.Client(),
    }
    
    // Override BaseURL for test
    oldBaseURL := BaseURL
    BaseURL = server.URL
    defer func() { BaseURL = oldBaseURL }()
    
    project, err := pm.CreateProject("Test", "test", nil)
    if err != nil {
        t.Fatalf("CreateProject failed: %v", err)
    }
    
    if project.Key != "test" {
        t.Errorf("Expected key 'test', got '%s'", project.Key)
    }
}
```

## Next Steps

- [Save SDK keys to .env](env-config.md)
- [Set up project cloning](project-cloning.md)
- [Build automation tools](admin-tooling.md)
