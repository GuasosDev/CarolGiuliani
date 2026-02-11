# Multichannel Communication System Implementation Plan

This plan outlines the implementation of a comprehensive multichannel communication system integrating WhatsApp Business and corporate email management into the existing Django project.

## User Review Required

> [!IMPORTANT]
> **WhatsApp Business API Requirements**
> This implementation assumes you have access to WhatsApp Business API (not WhatsApp Business App). You'll need:
> - A WhatsApp Business API account (through Meta or a Business Solution Provider)
> - A verified business phone number
> - Webhook URL for receiving messages (will be provided after implementation)
> 
> Please confirm you have or can obtain WhatsApp Business API access.

> [!IMPORTANT]
> **Email Account Configuration**
> The system will support Gmail, Outlook, and generic IMAP/SMTP accounts. For Gmail, you'll need to:
> - Enable "App Passwords" for each account (2FA must be enabled)
> - For Outlook/Office365, ensure IMAP/SMTP is enabled
> 
> Please confirm the email providers you plan to use.

> [!WARNING]
> **Real-time Communication Requirements**
> This implementation uses Django Channels for WebSocket support (real-time updates). This requires:
> - Redis server for channel layer backend
> - ASGI server (Daphne or Uvicorn) instead of WSGI
> - Additional server configuration for production deployment
> 
> Are you comfortable with these additional infrastructure requirements?

> [!CAUTION]
> **Database Migration Impact**
> This will add a new `communications` app with extensive database models. Existing data will not be affected, but the new app will create relationships with the existing [Client](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/clients/models.py#3-11) model.

## Proposed Changes

### New Django App: `communications`

A new Django app will be created to handle all multichannel communication functionality, keeping it modular and maintainable.

---

### Core Models and Infrastructure

#### [NEW] [models.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/models.py)

**Contact Model**: Extends/links to existing [Client](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/clients/models.py#3-11) model with communication-specific fields
- Links to existing `clients.Client` model
- Stores unified contact information
- Tracks preferred communication channel
- Maintains WhatsApp number and email addresses

**Conversation Model**: Unified conversation container for all channels
- Channel type (WhatsApp, Email)
- Status (open, assigned, closed, pending)
- Assigned agent (links to User model)
- Priority level
- Tags for categorization
- Created/updated timestamps

**Message Model**: Base message model for all channels
- Polymorphic relationship (can be WhatsApp or Email)
- Direction (inbound/outbound)
- Content and metadata
- Read status and timestamps
- Links to conversation and sender

**InternalNote Model**: Agent notes on conversations
- Links to conversation
- Author (User)
- Content and timestamps
- Visibility settings

**QuickReply Model**: Predefined message templates
- Title and content
- Channel type (WhatsApp, Email, or both)
- Category for organization
- Usage statistics

---

### WhatsApp Business Integration

#### [NEW] [models.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/models.py) (WhatsApp-specific models)

**WhatsAppAccount Model**:
- Business phone number
- WhatsApp Business API credentials
- Webhook verification token
- Status and configuration

**WhatsAppMessage Model**: Inherits from Message
- WhatsApp message ID
- Message type (text, image, document, etc.)
- Media URL and metadata
- Template information
- Delivery status

**ConversationAssignment Model**: Multi-agent assignment system
- Links conversation to agent
- Assignment timestamp
- Auto-assignment based on workload
- Assignment history

#### [NEW] [whatsapp_handler.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/whatsapp_handler.py)

WhatsApp Business API integration:
- Webhook endpoint handler for incoming messages
- Message sending functionality
- Media handling (images, documents, audio)
- Template message support
- Delivery status tracking
- Error handling and retry logic

#### [NEW] [assignment_system.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/assignment_system.py)

Intelligent conversation assignment:
- Load balancing algorithm (distributes based on active conversations)
- Round-robin assignment option
- Manual assignment override
- Reassignment functionality
- Queue management for unassigned conversations

---

### Email Integration

#### [NEW] [models.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/models.py) (Email-specific models)

**EmailAccount Model**:
- Email address
- Provider type (Gmail, Outlook, IMAP/SMTP)
- IMAP/SMTP credentials (encrypted)
- Sync settings and status
- Last sync timestamp

**EmailMessage Model**: Inherits from Message
- Email subject
- HTML and plain text body
- Headers (Message-ID, In-Reply-To, References)
- Thread ID for grouping
- Attachments

**EmailThread Model**: Groups related emails
- Subject line
- Participant list
- First and last message timestamps
- Links to conversation

**EmailTemplate Model**:
- Name and description
- Subject and body templates
- Variable placeholders ({{client_name}}, {{agent_name}}, etc.)
- Category

**EmailSignature Model**:
- User-specific signatures
- HTML and plain text versions
- Default signature flag

**EmailAttachment Model**:
- File storage
- Filename and MIME type
- Size and upload timestamp
- Links to email message

#### [NEW] [email_handler.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/email_handler.py)

Email synchronization and sending:
- IMAP connection and message fetching
- Email parsing and threading logic
- SMTP sending with retry queue
- Attachment handling
- HTML email rendering
- Template variable substitution

#### [NEW] [email_sync.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/email_sync.py)

Background email synchronization:
- Periodic sync task (every 5 minutes)
- Incremental sync (only new messages)
- Error handling and logging
- Sync status tracking

---

### Real-time Communication (WebSockets)

#### [NEW] [consumers.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/consumers.py)

Django Channels WebSocket consumer:
- Real-time message broadcasting
- User-specific message routing
- Conversation updates
- Typing indicators
- Online/offline status

#### [NEW] [routing.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/routing.py)

WebSocket URL routing configuration

#### [MODIFY] [asgi.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/gd_soft_gty/asgi.py)

Update ASGI configuration to support WebSockets

---

### API and Views

#### [NEW] [api/views.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/api/views.py)

REST API endpoints:
- Conversation list and detail
- Message sending and retrieval
- Contact management
- Template CRUD operations
- Assignment management
- Search and filtering
- Metrics and analytics

#### [NEW] [api/serializers.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/api/serializers.py)

Django REST Framework serializers for all models

#### [NEW] [api/permissions.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/api/permissions.py)

Custom permission classes:
- Agent: Can view assigned conversations, send messages
- Supervisor: Can view all conversations, reassign, access metrics
- Admin: Full access including account configuration

#### [NEW] [views.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/views.py)

Django views for web interface:
- Dashboard view (conversation list)
- Conversation detail view
- Contact 360° view
- Template management
- Settings and configuration
- Supervisor dashboard with metrics

---

### Frontend Templates and UI

#### [NEW] [templates/communications/dashboard.html](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/templates/communications/dashboard.html)

Main communication dashboard:
- Conversation list with filters
- Real-time updates via WebSocket
- Status indicators
- Quick actions

#### [NEW] [templates/communications/conversation_detail.html](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/templates/communications/conversation_detail.html)

Conversation view:
- Message thread display
- Send message form
- Quick reply buttons
- Internal notes section
- Contact information sidebar
- Channel-specific features (email threading, WhatsApp media)

#### [NEW] [templates/communications/contact_360.html](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/templates/communications/contact_360.html)

360° contact view:
- All conversations across channels
- Contact information
- Communication history timeline
- Notes and tags
- Related invoices/sales (integration with existing apps)

#### [NEW] [templates/communications/supervisor_dashboard.html](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/templates/communications/supervisor_dashboard.html)

Supervisor dashboard:
- Team performance metrics
- Response time statistics
- Conversation distribution
- Agent workload view
- Queue management

#### [NEW] [static/communications/js/websocket.js](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/static/communications/js/websocket.js)

WebSocket client for real-time updates

#### [NEW] [static/communications/css/communications.css](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/static/communications/css/communications.css)

Custom styles for communication interface

---

### Configuration and Settings

#### [MODIFY] [settings.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/gd_soft_gty/settings.py)

Add configurations:
- Add `communications` to `INSTALLED_APPS`
- Add `channels` and `rest_framework` to `INSTALLED_APPS`
- Configure Django Channels with Redis backend
- Add REST framework settings
- Add email backend configuration
- Add media file storage settings
- Configure Celery for background tasks (email sync)

#### [MODIFY] [urls.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/gd_soft_gty/urls.py)

Include communications URLs:
- Web interface routes
- API routes
- Webhook endpoints

#### [MODIFY] [requirements.txt](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/requirements.txt)

Add new dependencies:
- `channels` and `channels-redis` (WebSocket support)
- `djangorestframework` (API)
- `celery` and `redis` (background tasks)
- `requests` (WhatsApp API calls)
- Email libraries (already included in Python standard library)
- `cryptography` (for encrypting email credentials)

---

### Database Migrations

#### [NEW] [migrations/0001_initial.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/migrations/0001_initial.py)

Initial migration creating all communication models

---

### Background Tasks

#### [NEW] [tasks.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/tasks.py)

Celery tasks:
- Email synchronization task (runs every 5 minutes)
- Email sending queue processor
- Message delivery status updates
- Cleanup old conversations (optional)
- Generate daily/weekly reports

#### [NEW] [celery.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/gd_soft_gty/celery.py)

Celery configuration for the project

---

### Admin Interface

#### [NEW] [admin.py](file:///c:/Users/Chelo/Documents/GitHub/gd_soft_gty/communications/admin.py)

Django admin configuration:
- All model registrations
- Custom admin actions
- Inline editing for related models
- Search and filter configurations

## Verification Plan

### Automated Tests

#### Unit Tests
```bash
# Run all communication app tests
python manage.py test communications

# Test specific modules
python manage.py test communications.tests.test_models
python manage.py test communications.tests.test_whatsapp
python manage.py test communications.tests.test_email
python manage.py test communications.tests.test_api
```

Tests will cover:
- Model creation and relationships
- WhatsApp message parsing and sending
- Email threading logic
- Assignment algorithm
- API endpoints and permissions
- Template rendering

#### Integration Tests
```bash
# Test webhook endpoints
python manage.py test communications.tests.test_webhooks

# Test WebSocket connections
python manage.py test communications.tests.test_websockets
```

### Manual Verification

#### 1. WhatsApp Business Integration
**Prerequisites**: WhatsApp Business API account configured

Steps:
1. Navigate to Communications > Settings > WhatsApp Accounts
2. Add WhatsApp Business account credentials
3. Configure webhook URL (displayed after account creation)
4. Send a test message from a phone to the business number
5. Verify message appears in dashboard in real-time
6. Reply to the message from the dashboard
7. Confirm reply is received on the phone

#### 2. Email Synchronization
**Prerequisites**: Email account with existing messages

Steps:
1. Navigate to Communications > Settings > Email Accounts
2. Add an email account (Gmail/Outlook/IMAP)
3. Click "Sync Now" button
4. Verify existing emails are imported and threaded correctly
5. Send a new email to the configured account from external client
6. Wait 5 minutes or trigger manual sync
7. Verify new email appears in dashboard

#### 3. Multi-Agent Assignment
**Prerequisites**: Multiple user accounts with agent role

Steps:
1. Log in as admin
2. Create 3 test conversations (via API or by receiving messages)
3. Verify conversations are auto-assigned to different agents
4. Log in as agent 1 and verify assigned conversation appears
5. Log in as agent 2 and verify different conversation appears
6. As supervisor, manually reassign a conversation
7. Verify reassignment is reflected in both agents' dashboards

#### 4. Real-time Updates
**Prerequisites**: Two browser windows/tabs

Steps:
1. Open dashboard in two browser windows
2. Log in as different agents in each window
3. Send a message in one window
4. Verify message appears instantly in the other window (if same conversation)
5. Create a new conversation
6. Verify it appears in the conversation list without refresh

#### 5. 360° Contact View
**Prerequisites**: Contact with both WhatsApp and email conversations

Steps:
1. Navigate to a contact's 360° view
2. Verify all WhatsApp conversations are displayed
3. Verify all email threads are displayed
4. Verify timeline shows messages from both channels chronologically
5. Add an internal note
6. Verify note appears in the conversation detail view

#### 6. Template System
Steps:
1. Create a quick reply template with variables (e.g., "Hello {{client_name}}")
2. Open a conversation
3. Select the template from quick replies
4. Verify variables are replaced with actual contact data
5. Send the message
6. Verify it's sent correctly

### Performance Testing

```bash
# Load testing for API endpoints (requires locust or similar)
locust -f communications/tests/load_tests.py
```

Test scenarios:
- 100 concurrent agents accessing dashboard
- 50 messages per second webhook processing
- Email sync with 1000+ messages
- WebSocket connection stability with 100+ concurrent users

### User Acceptance Testing

After implementation, please test:
1. **Daily workflow**: Use the system for actual customer communications for 1-2 days
2. **Edge cases**: Test with various email formats, WhatsApp media types, special characters
3. **Permission system**: Verify agents can only access assigned conversations
4. **Supervisor features**: Test reassignment, metrics, and team overview
5. **Mobile responsiveness**: Test dashboard on mobile devices

Please provide feedback on:
- UI/UX improvements needed
- Missing features
- Performance issues
- Any bugs or unexpected behavior
