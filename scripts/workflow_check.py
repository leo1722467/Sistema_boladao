import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.ticket_workflow import TicketWorkflowEngine, TicketStatus
from app.core.exceptions import TicketError

def main() -> None:
    wf = TicketWorkflowEngine()
    # Valid transition NEW -> OPEN
    t1 = wf.validate_transition(TicketStatus.NEW, TicketStatus.OPEN, user_role="agent")
    print(f"NEW->OPEN: ok (to={t1.to_status})")

    # Invalid transition NEW -> PENDING_CUSTOMER
    try:
        wf.validate_transition(TicketStatus.NEW, TicketStatus.PENDING_CUSTOMER, user_role="agent")
        print("NEW->PENDING_CUSTOMER: ok")
    except TicketError as e:
        print(f"NEW->PENDING_CUSTOMER: error ({e})")

    # Valid sequence OPEN -> IN_PROGRESS
    t2 = wf.validate_transition(TicketStatus.OPEN, TicketStatus.IN_PROGRESS, user_role="agent")
    print(f"OPEN->IN_PROGRESS: ok (to={t2.to_status})")

if __name__ == "__main__":
    main()
