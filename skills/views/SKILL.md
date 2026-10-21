---
name: views
description: Manage Coralogix saved views and saved-view folders. Load when the user asks to create, update, delete, inspect, organize, or list saved log views.
metadata:
  author: coralogix
  version: 1.0.0
---

# Saved Views

Saved views preserve a logs query, time range, filters, and display mode for later reuse.

## Available Tools

| Task | Tool |
|---|---|
| List saved views | `list_views` |
| Get a saved view by ID | `get_view` |
| List saved-view folders | `list_view_folders` |
| Get a saved-view folder by ID | `get_view_folder` |
| Create, update, or delete a saved view | `manage_views` |
| Create, update, or delete a saved-view folder | `manage_view_folders` |

## Safe Workflow

1. Use `list_views` to identify an existing view or `get_view` to inspect its full definition.
2. For a new view, call `manage_views(action="create", body=...)`.
3. To modify a view, first fetch it with `get_view`, then call `manage_views(action="update", view_id=..., body=...)`.
4. Use `manage_views(action="delete", view_id=...)` only after the user explicitly confirms deletion.
5. Use `manage_view_folders` to create, update, or delete folders. Fetch an existing folder before updating it, and require explicit confirmation before deletion.

## View Request Bodies

Create and update use a flat JSON body; do not wrap it in a `view` object.

Create requires `name` and `timeSelection`. A minimal logs view is:

```json
{
  "name": "Recent errors",
  "viewType": "VIEW_TYPE_LOGS",
  "timeSelection": {
    "quickSelection": {
      "seconds": 3600
    }
  },
  "searchQuery": {
    "query": "source logs | limit 100",
    "syntaxType": "SYNTAX_TYPE_DATAPRIME"
  }
}
```

For updates, retain the existing fields and add the numeric `id` that matches `view_id`. `quickSelection` accepts `seconds`; the API supplies a display `caption` in responses, but do not send that response-only field in a write request.

`searchQuery` is optional, but when supplied it requires `query`. Use `VIEW_TYPE_LOGS` for log views. Optional `folderId` assigns the view to a saved-view folder.

## View Folder Request Bodies

`manage_view_folders` uses a flat body for `create` and `update`; `folder_id` is required for `update` and `delete`. For updates, the tool inserts `folder_id` into the API request body.
