# Node.js/TypeScript Project Setup

Implementation patterns for Node.js and TypeScript applications.

## Prerequisites

```bash
npm install axios dotenv
# or
yarn add axios dotenv
```

## TypeScript Project Manager

Create a typed module for project operations:

```typescript
// src/launchdarkly/projects.ts
import axios, { AxiosInstance } from 'axios';

interface Project {
  name: string;
  key: string;
  tags?: string[];
  environments?: {
    items: Environment[];
  };
}

interface Environment {
  name: string;
  key: string;
  apiKey: string;
}

interface CreateProjectParams {
  name: string;
  key: string;
  tags?: string[];
}

export class ProjectManager {
  private client: AxiosInstance;

  constructor(apiToken?: string) {
    const token = apiToken || process.env.LAUNCHDARKLY_API_TOKEN;
    if (!token) {
      throw new Error('LAUNCHDARKLY_API_TOKEN is required');
    }

    this.client = axios.create({
      baseURL: 'https://app.launchdarkly.com/api/v2',
      headers: {
        Authorization: token,
        'Content-Type': 'application/json',
      },
    });
  }

  async createProject(params: CreateProjectParams): Promise<Project> {
    try {
      const response = await this.client.post<Project>('/projects', params);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 409) {
        // Project exists, fetch and return it
        console.log(`Project '${params.key}' already exists`);
        return this.getProject(params.key);
      }
      throw error;
    }
  }

  async getProject(projectKey: string): Promise<Project> {
    const response = await this.client.get<Project>(`/projects/${projectKey}`, {
      params: { expand: 'environments' },
    });
    return response.data;
  }

  async getSdkKey(projectKey: string, environment: string = 'production'): Promise<string | null> {
    const project = await this.getProject(projectKey);
    const envItems = project.environments?.items || [];
    
    const env = envItems.find((e) => e.key === environment);
    return env?.apiKey || null;
  }

  async listProjects(): Promise<Project[]> {
    const response = await this.client.get<{ items: Project[] }>('/projects');
    return response.data.items;
  }
}
```

## JavaScript (CommonJS)

For Node.js without TypeScript:

```javascript
// src/launchdarkly/projects.js
const axios = require('axios');

class ProjectManager {
  constructor(apiToken) {
    const token = apiToken || process.env.LAUNCHDARKLY_API_TOKEN;
    if (!token) {
      throw new Error('LAUNCHDARKLY_API_TOKEN is required');
    }

    this.client = axios.create({
      baseURL: 'https://app.launchdarkly.com/api/v2',
      headers: {
        Authorization: token,
        'Content-Type': 'application/json',
      },
    });
  }

  async createProject({ name, key, tags = [] }) {
    try {
      const response = await this.client.post('/projects', { name, key, tags });
      return response.data;
    } catch (error) {
      if (error.response?.status === 409) {
        console.log(`Project '${key}' already exists`);
        return this.getProject(key);
      }
      throw error;
    }
  }

  async getProject(projectKey) {
    const response = await this.client.get(`/projects/${projectKey}`, {
      params: { expand: 'environments' },
    });
    return response.data;
  }

  async getSdkKey(projectKey, environment = 'production') {
    const project = await this.getProject(projectKey);
    const envItems = project.environments?.items || [];
    
    const env = envItems.find((e) => e.key === environment);
    return env?.apiKey || null;
  }

  async listProjects() {
    const response = await this.client.get('/projects');
    return response.data.items;
  }
}

module.exports = { ProjectManager };
```

## Express.js Integration

Integrate project setup into Express app:

```typescript
// src/app.ts
import express from 'express';
import dotenv from 'dotenv';
import { ProjectManager } from './launchdarkly/projects';

dotenv.config();

const app = express();
const pm = new ProjectManager();

// Ensure project exists on startup
async function initializeLaunchDarkly() {
  try {
    const project = await pm.createProject({
      name: 'Express API',
      key: 'express-api',
      tags: ['api', 'ai-configs'],
    });
    
    const sdkKey = await pm.getSdkKey('express-api', 'production');
    console.log(`✓ LaunchDarkly project ready: ${project.key}`);
    
    // Store SDK key for SDK initialization
    process.env.LD_SDK_KEY = sdkKey || '';
  } catch (error) {
    console.error('Failed to initialize LaunchDarkly:', error);
    process.exit(1);
  }
}

// Initialize before starting server
initializeLaunchDarkly().then(() => {
  app.listen(3000, () => {
    console.log('Server running on port 3000');
  });
});
```

## NestJS Integration

For NestJS applications:

```typescript
// src/launchdarkly/launchdarkly.module.ts
import { Module, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ProjectManager } from './projects';

@Module({
  providers: [ProjectManager],
  exports: [ProjectManager],
})
export class LaunchDarklyModule implements OnModuleInit {
  constructor(
    private readonly pm: ProjectManager,
    private readonly config: ConfigService,
  ) {}

  async onModuleInit() {
    const projectKey = this.config.get('LAUNCHDARKLY_PROJECT_KEY', 'nestjs-app');
    
    try {
      const project = await this.pm.createProject({
        name: 'NestJS Application',
        key: projectKey,
        tags: ['nestjs', 'ai-configs'],
      });
      
      console.log(`✓ LaunchDarkly project ready: ${project.key}`);
    } catch (error) {
      console.error('LaunchDarkly initialization failed:', error);
    }
  }
}


// src/launchdarkly/projects.ts (Injectable version)
import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance } from 'axios';

@Injectable()
export class ProjectManager {
  private client: AxiosInstance;

  constructor(private config: ConfigService) {
    const apiToken = this.config.get('LAUNCHDARKLY_API_TOKEN');
    this.client = axios.create({
      baseURL: 'https://app.launchdarkly.com/api/v2',
      headers: {
        Authorization: apiToken,
        'Content-Type': 'application/json',
      },
    });
  }

  // ... same methods as before
}
```

## CLI Tool

Create a CLI for project management:

```typescript
// cli/projects.ts
#!/usr/bin/env node
import { Command } from 'commander';
import { ProjectManager } from '../src/launchdarkly/projects';

const program = new Command();
const pm = new ProjectManager();

program
  .name('ld-projects')
  .description('LaunchDarkly project management CLI');

program
  .command('create <name> <key>')
  .description('Create a new project')
  .option('-t, --tags <tags...>', 'Project tags')
  .action(async (name: string, key: string, options: { tags?: string[] }) => {
    try {
      const project = await pm.createProject({ name, key, tags: options.tags });
      console.log(`✓ Created: ${project.name} (${project.key})`);
    } catch (error: any) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  });

program
  .command('list')
  .description('List all projects')
  .action(async () => {
    try {
      const projects = await pm.listProjects();
      projects.forEach((p) => {
        console.log(`- ${p.name} (${p.key})`);
      });
    } catch (error: any) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  });

program
  .command('get-key <projectKey>')
  .description('Get SDK key for a project')
  .option('-e, --env <environment>', 'Environment', 'production')
  .action(async (projectKey: string, options: { env: string }) => {
    try {
      const sdkKey = await pm.getSdkKey(projectKey, options.env);
      if (sdkKey) {
        console.log(sdkKey);
      } else {
        console.error(`Environment '${options.env}' not found`);
        process.exit(1);
      }
    } catch (error: any) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  });

program.parse();
```

**Usage:**
```bash
npm run ld-projects create "My Agent" my-ai -t ai-configs production
npm run ld-projects list
npm run ld-projects get-key my-ai --env production
```

## Error Handling

Add comprehensive error handling:

```typescript
export class LaunchDarklyError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: any
  ) {
    super(message);
    this.name = 'LaunchDarklyError';
  }
}

export class ProjectManager {
  async createProject(params: CreateProjectParams): Promise<Project> {
    try {
      const response = await this.client.post<Project>('/projects', params);
      return response.data;
    } catch (error: any) {
      if (error.response) {
        const status = error.response.status;
        if (status === 409) {
          return this.getProject(params.key);
        }
        if (status === 401) {
          throw new LaunchDarklyError('Invalid API token', status);
        }
        if (status === 403) {
          throw new LaunchDarklyError(
            'Insufficient permissions (need projects:write)',
            status
          );
        }
        throw new LaunchDarklyError(
          `API error: ${error.response.data.message || 'Unknown error'}`,
          status,
          error.response.data
        );
      }
      throw new LaunchDarklyError(`Request failed: ${error.message}`);
    }
  }
}
```

## Testing

Mock with Jest:

```typescript
// __tests__/projects.test.ts
import axios from 'axios';
import { ProjectManager } from '../src/launchdarkly/projects';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('ProjectManager', () => {
  let pm: ProjectManager;

  beforeEach(() => {
    mockedAxios.create.mockReturnValue(mockedAxios as any);
    pm = new ProjectManager('test-token');
  });

  it('should create a project', async () => {
    const mockProject = { name: 'Test', key: 'test', tags: [] };
    mockedAxios.post.mockResolvedValue({ data: mockProject });

    const project = await pm.createProject({ name: 'Test', key: 'test' });

    expect(project.key).toBe('test');
    expect(mockedAxios.post).toHaveBeenCalledWith('/projects', {
      name: 'Test',
      key: 'test',
    });
  });

  it('should handle existing project', async () => {
    const mockProject = { name: 'Test', key: 'test' };
    mockedAxios.post.mockRejectedValue({
      response: { status: 409 },
    });
    mockedAxios.get.mockResolvedValue({ data: mockProject });

    const project = await pm.createProject({ name: 'Test', key: 'test' });

    expect(project.key).toBe('test');
    expect(mockedAxios.get).toHaveBeenCalledWith('/projects/test', {
      params: { expand: 'environments' },
    });
  });
});
```

## Next Steps

- [Save SDK keys to .env](env-config.md)
- [Set up project cloning](project-cloning.md)
- [Build admin tooling](admin-tooling.md)
