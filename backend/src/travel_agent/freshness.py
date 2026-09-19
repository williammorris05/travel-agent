from datetime import datetime, timezone


def evidence_expired(snapshot) -> bool:
    if snapshot is None:
        return False
    now = datetime.now(timezone.utc)
    for option in snapshot.options:
        ttl = 300 if option.kind == 'hotel' else 30 * 86400 if option.kind == 'activity' else None
        if ttl is not None:
            for item in [*(cost.evidence for cost in option.costs), *option.supporting_evidence]:
                age = (now - item.retrieved_at).total_seconds()
                if age < 0 or age > ttl:
                    return True
    return False
