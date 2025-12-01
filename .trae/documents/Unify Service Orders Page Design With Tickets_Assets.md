## Overview
- Align Service Orders page visuals and interactions with Tickets and Assets pages: same header/sidebar layout, filter bar, card + count, table styling, loading/empty/error states, pagination, and authenticated fetch behavior.

## UI Structure
- Header: reuse the compact header with `menuToggle`, page title and quick links.
- Sidebar: same nav items and `collapsed/expanded` class toggles.
- Filters: identical inputs and buttons (`searchInput`, `applyFiltersBtn`, `clearFiltersBtn`) with consistent spacing and classes.
- Cards: wrap the list in a `.card` with `.card-header` and a count element (e.g., `soCount`).
- Table: use the same `.tickets-table` CSS class for consistent styling; columns: `Número OS`, `Chamado`, `Tipo`, `Início`, `Fim`, `Duração`, `APR`.
- States: implement `.loading` (spinner), `.empty-state`, and error blocks matching Tickets/Assets style.

## Frontend Logic
- Global State: `currentServiceOrders`, `currentPage`, `totalPages` (to match Tickets behavior).
- Initialization: `DOMContentLoaded` → check `access_token` cookie, `initializeEventListeners()`, `loadServiceOrders()`.
- Event Listeners: identical handlers for sidebar toggle, filter apply/clear, and Enter-to-search.
- Fetch:
  - Build `URLSearchParams` with `page` and `limit` and filters (`search`, `numero_apr`, `chamado_id`).
  - Include `Authorization: Bearer <token>` and `credentials: 'include'`.
  - Error handling: map HTTP 401/403/500 to user-friendly messages (same pattern used in Tickets).
- Rendering:
  - `showLoading()`, `showError(message)`, `renderSOTable()` mirroring Tickets’ DOM building approach.
  - Count: `updateSOCount(total)` updates the header count.
  - Pagination: build page buttons like Tickets (`Página X de Y`, left/right chevrons, active state), and re-fetch on click.

## Backend Alignment (Optional Enhancements)
- Add `page` → `offset` computation in `GET /api/helpdesk/service-orders` (like Tickets) for consistent pagination semantics.
- Extend `ServiceOrderListResponse` to include `page` and `total_pages` (if not already present), so the UI can show the same pagination controls.
- Ensure eager loading of relations (`tipo`, `chamado`) for stable response building (already proposed and aligned).

## Testing
- Authenticated user with appropriate role (`agent` or `admin`) loads `/service-orders`.
- Verify: filters, loading spinner, empty state, error messages, and pagination work identically to `/tickets` and `/assets`.
- Permission check: with insufficient role, UI shows consistent error message without breaking.

## Deliverables
- Updated `service_orders.html` mirroring layout and JS patterns of Tickets/Assets.
- (Optional) Backend pagination parity for Service Orders to fully match Tickets UI.

Confirm and I will implement the page updates and, if approved, the small backend pagination tweak for perfect parity.