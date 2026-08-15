import uuid
import datetime
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.product import Conflict as DBConflict, ProductTwin, ProductAttribute, ReviewDecision
from app.conflicts.models import ConflictResolutionRequest, ConflictStatus
from app.normalization.service import get_normalization_service

logger = logging.getLogger(__name__)


class ConflictResolutionService:
    """
    Service responsible for managing, resolving, and dismissing product attribute conflicts.
    Maintains an audit trail through ReviewDecision records without destroying history.
    """

    def __init__(self):
        self.normalizer = get_normalization_service()

    def resolve_conflict(
        self,
        db: Session,
        conflict_id: str,
        resolution: ConflictResolutionRequest,
    ) -> Optional[DBConflict]:
        """
        Resolve an active conflict with reviewer-selected value and audit rationale.
        """
        db_conflict = db.query(DBConflict).filter(DBConflict.id == conflict_id).first()
        if not db_conflict:
            logger.warning(f"Conflict not found: {conflict_id}")
            return None

        product_id = db_conflict.product_id
        attr_name = db_conflict.attribute
        selected_val = resolution.selected_value

        # Update conflict status
        db_conflict.status = ConflictStatus.RESOLVED.value

        # Update product attribute value if selected value provided
        db_attr = db.query(ProductAttribute).filter(
            ProductAttribute.product_id == product_id,
            ProductAttribute.name == attr_name
        ).first()

        prev_val = db_attr.value if db_attr else db_conflict.values

        if db_attr and selected_val is not None:
            db_attr.value = selected_val
            # Canonicalize normalized value
            norm_res = self.normalizer.normalize_attribute(attr_name, selected_val)
            db_attr.normalized_value = norm_res.normalized_value
            db_attr.unit = norm_res.unit
            db_attr.status = "VERIFIED"

        # Record ReviewDecision for complete audit trail
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        action_str = resolution.reviewer_action.value if hasattr(resolution.reviewer_action, "value") else str(resolution.reviewer_action)

        db_decision = ReviewDecision(
            id=decision_id,
            product_id=product_id,
            attribute=attr_name,
            previous_value=prev_val,
            selected_value=selected_val,
            reviewer_action=action_str,
            reason=resolution.reason,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(db_decision)

        # Check if any remaining OPEN conflicts exist on product
        open_conflicts = db.query(DBConflict).filter(
            DBConflict.product_id == product_id,
            DBConflict.status == ConflictStatus.OPEN.value,
            DBConflict.id != conflict_id
        ).count()

        product = db.query(ProductTwin).filter(ProductTwin.id == product_id).first()
        if product and open_conflicts == 0:
            product.status = "REVIEWED"

        db.commit()
        db.refresh(db_conflict)
        return db_conflict

    def dismiss_conflict(
        self,
        db: Session,
        conflict_id: str,
        reason: str,
    ) -> Optional[DBConflict]:
        """
        Dismiss a conflict (e.g. deemed acceptable variance or irrelevant).
        """
        db_conflict = db.query(DBConflict).filter(DBConflict.id == conflict_id).first()
        if not db_conflict:
            return None

        product_id = db_conflict.product_id
        db_conflict.status = ConflictStatus.DISMISSED.value

        # Record dismissal audit log
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        db_decision = ReviewDecision(
            id=decision_id,
            product_id=product_id,
            attribute=db_conflict.attribute,
            previous_value=db_conflict.values,
            selected_value=None,
            reviewer_action="DISMISS",
            reason=reason,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(db_decision)

        # Update product status if all conflicts cleared
        open_conflicts = db.query(DBConflict).filter(
            DBConflict.product_id == product_id,
            DBConflict.status == ConflictStatus.OPEN.value,
            DBConflict.id != conflict_id
        ).count()

        product = db.query(ProductTwin).filter(ProductTwin.id == product_id).first()
        if product and open_conflicts == 0:
            product.status = "REVIEWED"

        db.commit()
        db.refresh(db_conflict)
        return db_conflict

    def list_conflicts_for_product(
        self,
        db: Session,
        product_id: str,
        status: Optional[str] = None
    ) -> List[DBConflict]:
        query = db.query(DBConflict).filter(DBConflict.product_id == product_id)
        if status:
            query = query.filter(DBConflict.status == status.upper())
        return query.all()


_default_conflict_service: Optional[ConflictResolutionService] = None


def get_conflict_service() -> ConflictResolutionService:
    global _default_conflict_service
    if _default_conflict_service is None:
        _default_conflict_service = ConflictResolutionService()
    return _default_conflict_service
