# Sistema Boladão - User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Asset Management](#asset-management)
4. [Ticket Management](#ticket-management)
5. [Service Orders](#service-orders)
6. [Integrations](#integrations)
7. [User Roles & Permissions](#user-roles--permissions)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Getting Started

### System Requirements

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection
- JavaScript enabled

### First Login

1. Navigate to the Sistema Boladão login page
2. Enter your email and password
3. Click "Login" to access the system
4. You'll be redirected to the main dashboard

### Navigation

The system uses a sidebar navigation menu with the following sections:

- **Dashboard**: Overview and statistics
- **Ativos**: Asset management
- **Chamados**: Ticket management
- **Ordens de Serviço**: Service order management
- **Estoque**: Inventory management
- **Integrações**: External integrations
- **Relatórios**: Analytics and reports
- **Admin**: Administrative functions

## Dashboard Overview

The dashboard provides a comprehensive overview of your helpdesk operations:

### Key Metrics

- **Chamados Abertos**: Number of currently open tickets
- **SLA em Risco**: Tickets approaching SLA deadlines
- **Ordens Concluídas**: Completed service orders this week
- **Ativos Ativos**: Total active assets in the system

### Quick Actions

- **Flow Engine**: Configure custom workflows
- **Criar Chamado**: Create new tickets with guided interface
- **Gerenciar Tabelas**: Access administrative data management
- **Painel Administrativo**: Advanced system administration

### Recent Activity

View the latest system activities including:
- New tickets created
- Service orders completed
- SLA warnings
- System notifications

## Asset Management

### Viewing Assets

1. Click "Ativos" in the sidebar
2. Use the search and filter options to find specific assets:
   - **Search**: Enter tag, description, or serial number
   - **Status**: Filter by asset status (Active, Inactive, Maintenance)
   - **Type**: Filter by asset type (Computer, Printer, Monitor, etc.)
   - **Location**: Filter by installation location

### Asset Information

Each asset displays:
- **Tag**: Unique asset identifier
- **Description**: Asset description
- **Serial**: System-generated serial number
- **Type**: Asset category
- **Status**: Current operational status
- **Location**: Physical location

### Asset Actions

- **View**: See detailed asset information
- **Edit**: Modify asset details (requires permissions)
- **Delete**: Remove asset from system (requires permissions)

### Adding New Assets

1. Click "Novo Ativo" button
2. Fill in the required information:
   - Asset tag
   - Description
   - Type
   - Status
3. Click "Salvar" to create the asset

## Ticket Management

### Viewing Tickets

1. Click "Chamados" in the sidebar
2. View ticket statistics at the top:
   - Open tickets count
   - SLA risk indicators
   - Resolved tickets today
   - Overdue tickets

### Ticket Filters

Use the comprehensive filtering system:
- **Search**: Find tickets by number, title, or description
- **Status**: Filter by ticket status
- **Priority**: Filter by priority level
- **Agent**: Filter by assigned agent
- **SLA**: Filter by SLA status

### Ticket Information

Each ticket shows:
- **Number**: Unique ticket identifier
- **Title**: Brief description of the issue
- **Status**: Current ticket status with color coding
- **Priority**: Issue priority level
- **Agent**: Assigned technician
- **SLA**: Service level agreement status
- **Created**: When the ticket was opened

### Ticket Workflow

Tickets follow a defined workflow:

1. **New**: Newly created ticket
2. **Open**: Ticket assigned and acknowledged
3. **In Progress**: Work is being performed
4. **Pending Customer**: Waiting for customer response
5. **Resolved**: Issue has been fixed
6. **Closed**: Ticket completed and closed

### Working with Tickets

#### Viewing Ticket Details
1. Click on a ticket number to open details
2. Review all ticket information including:
   - Full description
   - Asset information
   - Current status and priority
   - SLA information
   - Activity history
   - Suggested next actions

#### Updating Tickets
1. Click "Edit" on a ticket
2. Modify status, priority, or assignment
3. Add resolution notes if resolving
4. Save changes

#### Workflow Visualization
1. Click the workflow icon on any ticket
2. View the current status in the workflow
3. See completed and pending steps
4. Understand next required actions

### Creating New Tickets

1. Click "Novo Chamado" button
2. You'll be redirected to the guided ticket creation flow
3. Follow the step-by-step process to provide all necessary information

## Service Orders

### Overview

Service orders track the actual work performed to resolve tickets. They provide detailed activity logging and time tracking.

### Viewing Service Orders

1. Click "Ordens de Serviço" in the sidebar
2. View service order statistics
3. Use filters to find specific orders

### Service Order Information

- **Number**: Unique service order identifier (OS-{company}-{year}-{sequence})
- **Related Ticket**: Associated ticket number
- **Status**: Current order status
- **Activities**: Work performed
- **Time Tracking**: Estimated vs. actual time
- **Technician**: Assigned service technician

### Service Order Workflow

1. **Draft**: Order created but not started
2. **Scheduled**: Work scheduled for specific time
3. **In Progress**: Work is being performed
4. **On Hold**: Work temporarily suspended
5. **Completed**: All work finished
6. **Cancelled**: Order cancelled
7. **Invoiced**: Work billed to customer
8. **Closed**: Order fully completed

### Activity Tracking

Service orders support detailed activity logging:
- **Description**: What work was performed
- **Time Spent**: Actual time for the activity
- **Type**: Category of work (diagnostic, repair, etc.)
- **Notes**: Additional details

### Analytics

View comprehensive service order analytics:
- Total service orders
- Completion rates
- Average completion times
- Billable hours tracking
- Monthly trends

## Integrations

### WhatsApp Integration

Send automated notifications to customers:
- Ticket creation confirmations
- Status update notifications
- Resolution confirmations
- Custom messages

### AI Gateway

Leverage artificial intelligence for:
- **Ticket Classification**: Automatic categorization
- **Priority Assessment**: AI-suggested priorities
- **Sentiment Analysis**: Customer satisfaction monitoring
- **Solution Suggestions**: Recommended actions

### Webhook Management

Configure external system integrations:
- Set up webhook endpoints
- Configure event types
- Monitor delivery status
- Test webhook functionality

## User Roles & Permissions

### Admin
- Full system access
- User management
- System configuration
- Integration management
- All CRUD operations

### Agent
- Ticket management
- Service order management
- Asset viewing
- Customer communication
- Workflow operations

### Requester
- Create tickets
- View own tickets
- Update ticket information
- Communicate with agents

### Viewer
- Read-only access
- View tickets and assets
- Generate reports
- Monitor system status

## Best Practices

### Ticket Management

1. **Clear Titles**: Use descriptive, specific titles
2. **Detailed Descriptions**: Provide comprehensive problem descriptions
3. **Proper Categorization**: Select appropriate priority and category
4. **Regular Updates**: Keep tickets updated with progress
5. **Complete Resolution**: Provide detailed resolution notes

### Asset Management

1. **Consistent Naming**: Use standardized asset tags
2. **Regular Updates**: Keep asset information current
3. **Location Tracking**: Maintain accurate location data
4. **Status Management**: Update status as assets change

### Service Orders

1. **Detailed Activities**: Log all work performed
2. **Accurate Time Tracking**: Record actual time spent
3. **Complete Documentation**: Include all relevant details
4. **Customer Communication**: Keep customers informed

### Security

1. **Strong Passwords**: Use complex, unique passwords
2. **Regular Logout**: Log out when finished
3. **Access Control**: Only access necessary information
4. **Report Issues**: Report security concerns immediately

## Troubleshooting

### Common Issues

#### Cannot Login
- Verify email and password
- Check for caps lock
- Contact administrator for password reset
- Ensure account is active

#### Page Not Loading
- Refresh the browser
- Clear browser cache
- Check internet connection
- Try different browser

#### Missing Data
- Check filter settings
- Verify permissions
- Refresh the page
- Contact support if data is missing

#### Slow Performance
- Close unnecessary browser tabs
- Clear browser cache
- Check internet speed
- Report persistent issues

### Error Messages

#### "Access Denied"
- Insufficient permissions for the action
- Contact administrator for access
- Verify you're logged in correctly

#### "Rate Limit Exceeded"
- Too many requests in short time
- Wait a few minutes before trying again
- Contact support if persistent

#### "Validation Error"
- Check required fields
- Verify data format
- Review input constraints
- Correct errors and retry

### Getting Help

#### In-System Help
- Look for help icons (?) throughout the interface
- Check tooltips on form fields
- Review validation messages

#### Contact Support
- Email: support@sistemaboladao.com
- Include error messages
- Describe steps to reproduce
- Provide browser and system information

#### Documentation
- API Documentation: For technical integrations
- User Guide: This document
- Admin Guide: For system administrators

## Keyboard Shortcuts

### Global Shortcuts
- `Ctrl + /`: Open search
- `Ctrl + H`: Go to dashboard
- `Ctrl + T`: Create new ticket
- `Ctrl + A`: Go to assets
- `Ctrl + S`: Go to service orders

### Ticket Management
- `Ctrl + N`: New ticket
- `Ctrl + E`: Edit current ticket
- `Ctrl + R`: Resolve ticket
- `Ctrl + C`: Close ticket

### Navigation
- `Ctrl + 1-9`: Navigate to sidebar items
- `Ctrl + B`: Toggle sidebar
- `Esc`: Close modals/dialogs

## Mobile Usage

The system is fully responsive and works on mobile devices:

### Mobile Navigation
- Tap the menu icon to open/close sidebar
- Swipe left/right on tables for horizontal scrolling
- Use pull-to-refresh on lists

### Mobile Limitations
- Some advanced features may be simplified
- File uploads may have restrictions
- Complex forms may require landscape orientation

## Data Export

### Exporting Data
1. Navigate to the desired section
2. Apply any necessary filters
3. Look for export options (usually in the top-right)
4. Select export format (CSV, Excel, PDF)
5. Download the generated file

### Available Exports
- Ticket lists with filters
- Asset inventories
- Service order reports
- Analytics data
- Audit logs (admin only)

## System Maintenance

### Scheduled Maintenance
- System maintenance is typically scheduled during off-hours
- Users will be notified in advance
- Maintenance windows are usually 1-2 hours
- Critical updates may require immediate maintenance

### Backup and Recovery
- Data is automatically backed up daily
- Point-in-time recovery is available
- Contact support for data recovery requests
- Regular backup testing ensures data integrity

## Compliance and Security

### Data Protection
- All data is encrypted in transit and at rest
- Access is logged and monitored
- Regular security audits are performed
- GDPR compliance measures are in place

### Audit Trail
- All user actions are logged
- Audit logs are available to administrators
- Data changes are tracked with timestamps
- User access is monitored and reported

This user guide provides comprehensive information for using Sistema Boladão effectively. For additional support or questions not covered in this guide, please contact our support team.