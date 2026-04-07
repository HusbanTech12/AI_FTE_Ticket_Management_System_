# FlowSync Product Documentation

## Quick Start Guide

### Getting Started
1. **Create Account**: Sign up at flowsync.com with your email
2. **Verify Email**: Check inbox for verification link (valid 24 hours)
3. **Initial Setup**: Complete onboarding wizard (5-10 minutes)
4. **Invite Team**: Add team members via email invitation
5. **Create First Project**: Click "New Project" in dashboard

### Platform Access
- **Web App**: app.flowsync.com
- **iOS App**: Available on App Store (search "FlowSync")
- **Android App**: Available on Google Play Store
- **API**: api.flowsync.com with OAuth 2.0

## Feature Documentation

### Project Management
**Creating a Project**
1. Click "Projects" in left sidebar
2. Click "New Project" button
3. Enter project name and description
4. Select visibility (private/team/public)
5. Add team members (optional at creation)
6. Click "Create Project"

**Adding Tasks**
1. Open a project
2. Click "Add Task" in Tasks tab
3. Fill in: title, description, assignee, due date, priority
4. Click "Create Task"

**Task Statuses**
- Todo: Not started
- In Progress: Work in progress
- Review: Awaiting review/approval
- Done: Completed

### Integrations

#### Setting Up Slack Integration
1. Go to Settings → Integrations
2. Find Slack and click "Connect"
3. Authorize FlowSync in Slack workspace
4. Select channels to post updates to
5. Configure which events trigger notifications

**Supported Events**: Task assignments, due date reminders, project updates, comments

#### GitHub Integration
1. Settings → Integrations → GitHub
2. Connect your GitHub organization
3. Link repositories to FlowSync projects
4. Automatically creates tasks from GitHub issues
5. Updates task status based on PR merges

#### Google Drive Integration
- Link Google account in Settings → Integrations
- Attach files from Google Drive to tasks/comments
- Automatic permission sync
- View Google Docs previews without leaving FlowSync

### Time Tracking

**Manual Time Entry**
1. Open task
2. Click "Time" tab
3. Enter hours and optional description
4. Click "Save"

**Timer Mode**
1. Click play button on any task
2. Work in other apps
3. Click stop when done
4. Time automatically logged

**Reports**
- Access via Reports → Time Tracking
- Filter by project, team member, date range
- Export as CSV or PDF
- Billable vs non-billable hours toggle

### API Reference

#### Authentication
All API requests require OAuth 2.0 bearer token:
```
Authorization: Bearer {access_token}
```

#### Endpoints

**List Projects**
```
GET /api/v1/projects
Response: { "projects": [{ "id": "...", "name": "...", ... }] }
```

**Create Task**
```
POST /api/v1/tasks
Body: {
  "project_id": "...",
  "title": "...",
  "description": "...",
  "assignee_id": "...",  // optional
  "due_date": "2025-04-15",  // optional
  "priority": "high|medium|low"
}
```

**Update Task**
```
PATCH /api/v1/tasks/{task_id}
Body: { "status": "in_progress" }  // partial update
```

**Webhooks**
Configure webhooks in Settings → API → Webhooks
Events: task.created, task.updated, project.created, comment.added

Payload includes resource data and timestamp.

## Billing & Subscription

### Plans Comparison
| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| Users | 10 max | Unlimited | Unlimited |
| Projects | 50 | Unlimited | Unlimited |
| Storage | 10 GB | 100 GB | Unlimited |
| Integrations | 5 | All | All + Custom |
| Support | Email | Email + Chat | Dedicated Manager |
| SLA | - | 99.5% | 99.9% |
| SSO | - | - | ✓ |
| Audit Log | - | ✓ | ✓ |

### Managing Subscription
- **Upgrade/Downgrade**: Settings → Billing → Plan
- **Update Payment Method**: Settings → Billing → Payment Methods
- **View Invoices**: Settings → Billing → Invoices (download PDF)
- **Cancel Subscription**: Settings → Billing → Cancel Plan (effective at period end)

### Refund Policy
- 30-day money-back guarantee for new subscriptions
- Prorated refunds for annual plans canceled mid-year
- Contact billing@flowsync.com for refund requests

## Account Security

### Two-Factor Authentication (2FA)
1. Settings → Security → Two-Factor Authentication
2. Click "Enable 2FA"
3. Scan QR code with authenticator app (Google Authenticator, Authy)
4. Enter 6-digit code to verify
5. Save backup codes (download or print)

### Single Sign-On (SSO) - Enterprise Only
- Supports SAML 2.0 and OIDC
- Configure in Settings → Security → SSO
- Requires Enterprise plan
- Contact support@flowsync.com for setup assistance

### Password Reset
1. Go to login page
2. Click "Forgot password?"
3. Enter email address
4. Check inbox for reset link (expires 1 hour)
5. Create new password (min 8 chars, must include number)

## Data Export & Migration

### Export Your Data
**All Data Export**
- Settings → Data & Privacy → Export All Data
- Includes projects, tasks, comments, files, time entries
- Format: JSON
- Email delivered within 24 hours

**CSV Export**
- Projects: Projects list → Export CSV
- Tasks: Project → Tasks → Export CSV
- Time entries: Reports → Export CSV

### Migration Assistance
- Enterprise customers receive free migration support
- Import tools available for: Asana, Trello, Jira, Monday.com
- Contact support@flowsync.com to schedule migration

## Troubleshooting

### Common Issues

**Can't log in**
- Verify email format: user@company.com
- Check for typos
- Use "Forgot password?" to reset
- Contact support if 2FA issues

**Integrations not working**
- Re-authorize connection in Settings → Integrations
- Check API token hasn't expired
- Verify webhook URLs are accessible
- Review integration logs in Settings → Integrations → Logs

**Slow performance**
- Clear browser cache
- Disable browser extensions
- Try incognito mode
- Check internet connection
- Report to support if persistent

**Missing data after export**
- Large exports may take up to 24 hours
- Check spam folder for download email
- Contact support if not received within 48 hours

## Support Channels
- **Email**: support@flowsync.com (24-48 hour response)
- **Chat**: Available in app for Professional+ plans (9am-5pm PST)
- **Phone**: Enterprise customers only
- **Documentation**: help.flowsync.com
- **Community Forum**: community.flowsync.com
