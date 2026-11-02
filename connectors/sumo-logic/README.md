# Connect Sumo Logic to AWS DevOps Agent

Complete these steps in Sumo Logic before connecting.

## 1. Find your deployment

In Sumo Logic, open your profile menu and note the deployment in your URL (for example `service.us2.sumologic.com` is **US2**). Pick the matching region label when connecting. Labels: US1, US2, EU, DE, JP, AU, KR, CA, FED.

## 2. Create an OAuth client

You need the Administrator role, or a role that can manage OAuth clients.

1. Create an **Authorization Code** OAuth client.
2. Add the redirect (callback) URLs that the DevOps Agent console shows for your AWS region.
3. Under **Scopes**, expand each category and select only the **View** checkboxes for the resources listed in step 3 below, plus Run Log Search. Leave every **Manage** checkbox cleared. If you leave scopes unchecked, the client is granted all of them, and some scopes, such as Manage Library (create and update dashboards), are granted whatever the user's role, so a role alone can't remove dashboard writes.
4. Copy the **client ID** and **client secret**. The secret is shown once.

Sumo Logic supports PKCE (S256) on its authorization server, and DevOps Agent sends the challenge. There is no setting to turn on.

## 3. Check permissions

The agent acts as the person who signs in, so it can only do what that user's roles allow. For investigations, a role with these capabilities is enough: View Partitions, View Field Extraction Rules, View Fields, Run Log Search, View Alerts (Monitors), View Library (dashboards), and, for SIEM insights, View CSE.

Write tools exist (create dashboards, detection rules, update insights). Clearing the Manage scopes in step 2 removes them from the connection. If you keep them, leave them disabled or require approval in DevOps Agent unless you want the agent to change Sumo Logic content.

## 4. Connect

Return to the DevOps Agent console, choose the region, and enter the client ID and secret.
