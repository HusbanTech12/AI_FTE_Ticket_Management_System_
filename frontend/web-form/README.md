# FlowSync Support Web Form

A responsive, accessible support request form for TechCorp SaaS customers.

## Features

- **Responsive Design**: Works on mobile, tablet, and desktop
- **Client-side Validation**: Real-time input validation with helpful error messages
- **Accessibility**: ARIA labels, focus states, keyboard navigation
- **Loading States**: Visual feedback during submission
- **Success State**: Clear confirmation with ticket ID
- **Analytics Ready**: Includes tracking hooks for Google Analytics

## Quick Start

### Prerequisites
- Node.js 18+
- npm or yarn
- Backend API running (see parent README)

### Installation

```bash
cd frontend/web-form
npm install
```

### Development

```bash
# Start dev server on http://localhost:3000
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

### Environment Variables

The form interacts with the backend API. Configure the API endpoint:

```env
NEXT_PUBLIC_API_URL=https://api.flowsync-support.com
```

## Component Usage

### Standalone React Component

```jsx
import SupportForm from './SupportForm';

function Page() {
  return (
    <div>
      <h1>Contact Support</h1>
      <SupportForm apiEndpoint="/api/support/submit" />
    </div>
  );
}
```

### Embedding in Existing Site

```html
<!DOCTYPE html>
<html>
  <head>
    <title>FlowSync Support</title>
  </head>
  <body>
    <div id="support-form-root"></div>

    <script src="bundle.js"></script>
    <script>
      ReactDOM.render(
        React.createElement(SupportForm, {
          apiEndpoint: "https://api.flowsync-support.com/api/support/submit"
        }),
        document.getElementById('support-form-root')
      );
    </script>
  </body>
</html>
```

## API Integration

The form expects the backend to implement:

### POST `/api/support/submit`

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "subject": "Cannot reset password",
  "category": "technical",
  "priority": "medium",
  "message": "I'm getting an error..."
}
```

**Response (200 OK):**
```json
{
  "ticket_id": "abc123-def456",
  "message": "Thank you for contacting us! Our AI assistant will review your request...",
  "estimated_response_time": "Usually within 5 minutes"
}
```

**Error Response (4xx/5xx):**
```json
{
  "detail": "Invalid email address"
}
```

### GET `/api/support/ticket/{ticket_id}`

Returns ticket status and conversation history.

## Form Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| name | text | yes | min 2 chars |
| email | email | yes | valid email format |
| subject | text | yes | min 5, max 300 chars |
| category | select | yes | one of predefined |
| priority | select | no | low/medium/high |
| message | textarea | yes | min 10, max 3000 chars |

## Customization

### Styling

The component uses Tailwind CSS classes. You can override by:

1. **Replace Tailwind**: Swap utility classes for your CSS framework
2. **Custom wrapper**: Wrap the component and style via CSS:
   ```css
   .support-form-container { background: white; }
   ```

### Theme Colors

Change color tokens in `SupportForm.jsx`:

```jsx
// Replace:
className="bg-blue-600 hover:bg-blue-700"
// With:
className="bg-[your-color] hover:bg-[your-hover-color]"
```

### Validation Messages

Edit validation logic in `handleSubmit` and `validateForm` functions.

## Performance

- **Lazy loading**: Component can be loaded via dynamic import
- **Code splitting**: Next.js automatically splits
- **Bundle size**: ~15 kB gzipped (without Next.js)

## Browser Support

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## Accessibility

- WCAG 2.1 AA compliant
- Proper label associations
- Focus visible states
- Screen reader announcements
- Error announcements via `aria-live`

## Security

- CSRF protection (handled by backend)
- XSS prevention (escape user input in responses)
- Rate limiting (backend)
- CORS configured appropriately

## Testing

```bash
# Run unit tests (if configured)
npm test

# E2E tests with Cypress (optional)
npx cypress open
```

## Deployment

### Vercel/Netlify

```bash
npm run build
# Deploy .next folder
```

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## Support

For issues with the form component, contact TechCorp engineering.

## License

Proprietary - TechCorp SaaS © 2025
