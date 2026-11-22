# Service Hub

A booking and service management platform with integrated mobile payment support using Safaricom Daraja API.

## Architecture Overview

This project follows the **Client-Based Service Architecture (CBSE)** pattern:

- **Client-Agnostic Design**: The backend serves multiple clients (web, mobile, third-party integrations) through a unified REST API.
- **Service-Oriented Core**: Business logic is encapsulated in dedicated service classes (PaymentService, BookingService, etc.) that can be consumed by any client.
- **Provider Pattern**: External integrations (Safaricom Daraja API) are abstracted behind provider clients, enabling easy swapping or mocking.
- **Event-Driven Communication**: Services communicate via an outbox pattern for reliable event publishing.

### Project Structure

```
Service-Hub/
+-- config/                 # Django project settings
+-- service_hub/            # Main project package
¦   +-- apps/
¦       +-- bookings/       # Booking management
¦       +-- businesses/     # Business entities
¦       +-- service_catalog/ # Service catalog
¦       +-- availability/   # Availability scheduling
¦       +-- payments/       # Payment processing (Daraja)
¦       +-- notifications/  # Notifications (email)
¦       +-- events/         # Event sourcing/outbox
```

## Payment Integration (Safaricom Daraja)

### Overview

The payment system integrates with Safaricom's Daraja API for M-Pesa STK Push payments.

###-Key Components

1. **DarajaClient** (`apps/payments/providers/mpesa.py`)
   - Handles authentication (OAuth2 client credentials)
   - Initiates STK Push requests
   - Manages phone number normalization

2. **PaymentService** (`apps/payments/services.py`)
   - Creates and manages payment records
   - Processes callbacks from Daraja
   - Handles payment reversals

3. **PaymentCallbackView** (`apps/payments/views.py`)
   - Receives STK Push callbacks from Safaricom
   - Validates and processes payment outcomes

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/payment/ | Create a new payment |
| POST | /api/payment/initiate/ | Initiate STK Push for a booking |
| GET | /api/payment/booking-summary/ | Get booking payment summary |
| POST | /api/payments/payment/callback/ | Receive Daraja callbacks |

### Configuration

Required environment variables (`.env`):

```
MPESA_ENVIRONMENT=sandbox  # or production
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://your-domain.com/api/payments/payment/callback/
```

## Software Architecture

### Client-Based Service Architecture (CBSE)

This project implements the **Client-Based Service Architecture** pattern:

1. **Client Agnostic**: The backend provides a unified API that can be consumed by any client (web, mobile, partner apps) without modification.

2. **Service Encapsulation**: Business logic is encapsulated in dedicated service classes:
   - `PaymentService` - Payment lifecycle management
   - `BookingService` - Booking operations
   - `NotificationService` - Notification delivery

3. **Provider Pattern**: External integrations are abstracted behind provider clients:
   - `DarajaClient` - Safaricom API client
   - Enables easy testing, mocking, and future provider swaps.

4. **Event-Driven Outbox**: The `apps/events` module implements the outbox pattern for reliable event publishing to downstream consumers.

### Benefits

- **Decoupled Clients**: Clients don't need to know about each other's existence.
- **Extensible**: New clients can be added without changing core business logic.
- **Testable**: Service layer can be unit tested independently of HTTP concerns.
- **Maintainable**: Clear separation of concerns across modules.

## Development

### Setup

```bash
python -m venv venv
.\[venv]Scripts\activate\n# Install dependencies
pip install -rrequirements.txt\n# Run migrations
python manage.py migrate\n# Runserver
python manage.py runserver
```

## Testing

```bash
python manage.py test
```

## License

MIT
