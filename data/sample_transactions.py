import random
import uuid
from datetime import datetime, timedelta
from models.schemas import Transaction, TransactionType, RecipientType

# ---------------------------------------------------------------------------
# Seed data pools
# ---------------------------------------------------------------------------

SENDER_ACCOUNTS = [f"ACC-ID-{str(i).zfill(6)}" for i in range(1, 51)]
RECIPIENT_ACCOUNTS = [f"RCP-ID-{str(i).zfill(6)}" for i in range(1, 101)]
DEVICE_IDS = [f"DEV-{uuid.uuid4().hex[:8].upper()}" for _ in range(20)]

HIGH_RISK_COUNTRIES = ["NG", "KP", "IR", "MM", "VN", "CN", "RU"]
NORMAL_COUNTRIES = ["ID", "ID", "ID", "ID", "SG", "MY", "AU"]

BLACKLISTED_RECIPIENTS = [f"BLK-{str(i).zfill(4)}" for i in range(1, 6)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _txn_id(dt: datetime) -> str:
    return f"TXN-{dt.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def _random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def _daytime_ts(base: datetime | None = None) -> datetime:
    """Return a timestamp during business hours (08:00–17:59)."""
    base = base or datetime.now()
    return base.replace(
        hour=random.randint(8, 17),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    )


def _night_ts(base: datetime | None = None) -> datetime:
    """Return a timestamp during night hours (21:00–05:59)."""
    base = base or datetime.now()
    night_hour = random.choice(list(range(21, 24)) + list(range(0, 6)))
    return base.replace(
        hour=night_hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    )


def _recent_base() -> datetime:
    """Random datetime in the past 30 days."""
    return datetime.now() - timedelta(days=random.randint(0, 30))


# ---------------------------------------------------------------------------
# Per-tier builders
# ---------------------------------------------------------------------------

def _normal_transaction() -> Transaction:
    """~60% share: low-risk, expected behaviour."""
    base = _daytime_ts(_recent_base())
    amount = random.uniform(100_000, 10_000_000)
    return Transaction(
        transaction_id=_txn_id(base),
        transaction_type=random.choice([
            TransactionType.DOMESTIC_TRANSFER,
            TransactionType.INTERBANK_TRANSFER,
        ]),
        amount=round(amount, 0),
        currency="IDR",
        timestamp=base,
        sender_account_id=random.choice(SENDER_ACCOUNTS),
        sender_account_age_days=random.randint(365, 2000),
        recipient_account_id=random.choice(RECIPIENT_ACCOUNTS),
        recipient_type=RecipientType.EXISTING,
        recipient_country="ID",
        device_id=random.choice(DEVICE_IDS),
        ip_address=_random_ip(),
        is_night_transaction=False,
        sim_changed_recently=False,
        is_new_device=False,
        memo=random.choice([
            "Pembayaran tagihan",
            "Transfer gaji",
            "Biaya operasional",
            "Pembayaran supplier",
            "",
        ]),
        avg_monthly_txn_count=random.randint(5, 20),
        avg_transaction_amount=random.uniform(2_000_000, 8_000_000),
        usual_transaction_hours="09:00-18:00",
        recent_alerts_30d=0,
        daily_txn_count_today=random.randint(1, 3),
        daily_amount_today=round(amount, 0),
    )


def _medium_risk_transaction() -> Transaction:
    """~25% share: one or two suspicious indicators."""
    base = _recent_base()
    risk_flavour = random.choice(["new_recipient_large", "night_high_freq"])

    if risk_flavour == "new_recipient_large":
        ts = _daytime_ts(base)
        amount = random.uniform(10_000_000, 100_000_000)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.INTERBANK_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(180, 365),
            recipient_account_id=f"NEW-RCP-{random.randint(1000, 9999)}",
            recipient_type=RecipientType.NEW,
            recipient_country="ID",
            device_id=random.choice(DEVICE_IDS),
            ip_address=_random_ip(),
            is_night_transaction=False,
            sim_changed_recently=False,
            is_new_device=False,
            memo="Transfer bisnis baru",
            avg_monthly_txn_count=random.randint(5, 15),
            avg_transaction_amount=random.uniform(3_000_000, 7_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 1),
            daily_txn_count_today=random.randint(1, 4),
            daily_amount_today=round(amount, 0),
        )
    else:  # night_high_freq
        ts = _night_ts(base)
        amount = random.uniform(5_000_000, 50_000_000)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.DOMESTIC_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(200, 800),
            recipient_account_id=random.choice(RECIPIENT_ACCOUNTS),
            recipient_type=RecipientType.EXISTING,
            recipient_country="ID",
            device_id=random.choice(DEVICE_IDS),
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=False,
            is_new_device=False,
            memo="",
            avg_monthly_txn_count=random.randint(5, 12),
            avg_transaction_amount=random.uniform(2_000_000, 6_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 2),
            daily_txn_count_today=random.randint(5, 10),
            daily_amount_today=round(amount * random.uniform(2, 4), 0),
        )


def _high_risk_transaction() -> Transaction:
    """~15% share: multiple fraud indicators stacked."""
    base = _recent_base()
    pattern = random.choice([
        "new_account_large_night",
        "sim_swap_new_device",
        "split_to_new_recipients",
        "blacklisted_recipient",
        "high_risk_remittance",
    ])

    ts = _night_ts(base)

    if pattern == "new_account_large_night":
        amount = random.uniform(50_000_000, 500_000_000)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.INTERBANK_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(1, 30),
            recipient_account_id=f"NEW-RCP-{random.randint(1000, 9999)}",
            recipient_type=RecipientType.NEW,
            recipient_country="ID",
            device_id=f"NEW-DEV-{uuid.uuid4().hex[:8].upper()}",
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=False,
            is_new_device=True,
            memo="",
            avg_monthly_txn_count=random.randint(0, 3),
            avg_transaction_amount=random.uniform(500_000, 2_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 1),
            daily_txn_count_today=random.randint(1, 3),
            daily_amount_today=round(amount, 0),
        )

    elif pattern == "sim_swap_new_device":
        amount = random.uniform(30_000_000, 200_000_000)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.INTERBANK_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(90, 500),
            recipient_account_id=f"NEW-RCP-{random.randint(1000, 9999)}",
            recipient_type=RecipientType.NEW,
            recipient_country="ID",
            device_id=f"NEW-DEV-{uuid.uuid4().hex[:8].upper()}",
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=True,
            is_new_device=True,
            memo="",
            avg_monthly_txn_count=random.randint(3, 10),
            avg_transaction_amount=random.uniform(1_000_000, 5_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 2),
            daily_txn_count_today=random.randint(1, 4),
            daily_amount_today=round(amount, 0),
        )

    elif pattern == "split_to_new_recipients":
        # Simulate one leg of a structuring/splitting scheme
        amount = random.uniform(4_000_000, 9_900_000)  # just below round thresholds
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.DOMESTIC_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(30, 180),
            recipient_account_id=f"NEW-RCP-{random.randint(1000, 9999)}",
            recipient_type=RecipientType.NEW,
            recipient_country="ID",
            device_id=random.choice(DEVICE_IDS),
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=False,
            is_new_device=False,
            memo="",
            avg_monthly_txn_count=random.randint(2, 8),
            avg_transaction_amount=random.uniform(500_000, 2_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(1, 3),
            daily_txn_count_today=random.randint(8, 20),   # many splits today
            daily_amount_today=round(amount * random.uniform(8, 15), 0),
        )

    elif pattern == "blacklisted_recipient":
        amount = random.uniform(10_000_000, 150_000_000)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.INTERBANK_TRANSFER,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(60, 400),
            recipient_account_id=random.choice(BLACKLISTED_RECIPIENTS),
            recipient_type=RecipientType.BLACKLISTED,
            recipient_country="ID",
            device_id=random.choice(DEVICE_IDS),
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=random.choice([True, False]),
            is_new_device=random.choice([True, False]),
            memo="",
            avg_monthly_txn_count=random.randint(2, 10),
            avg_transaction_amount=random.uniform(1_000_000, 4_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 3),
            daily_txn_count_today=random.randint(1, 5),
            daily_amount_today=round(amount, 0),
        )

    else:  # high_risk_remittance
        amount = random.uniform(20_000_000, 300_000_000)
        country = random.choice(HIGH_RISK_COUNTRIES)
        return Transaction(
            transaction_id=_txn_id(ts),
            transaction_type=TransactionType.INTERNATIONAL_REMITTANCE,
            amount=round(amount, 0),
            currency="IDR",
            timestamp=ts,
            sender_account_id=random.choice(SENDER_ACCOUNTS),
            sender_account_age_days=random.randint(30, 200),
            recipient_account_id=f"INTL-{country}-{random.randint(10000, 99999)}",
            recipient_type=RecipientType.NEW,
            recipient_country=country,
            device_id=f"NEW-DEV-{uuid.uuid4().hex[:8].upper()}",
            ip_address=_random_ip(),
            is_night_transaction=True,
            sim_changed_recently=True,
            is_new_device=True,
            memo="",
            avg_monthly_txn_count=random.randint(1, 5),
            avg_transaction_amount=random.uniform(500_000, 3_000_000),
            usual_transaction_hours="09:00-18:00",
            recent_alerts_30d=random.randint(0, 2),
            daily_txn_count_today=random.randint(1, 3),
            daily_amount_today=round(amount, 0),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_transactions(count: int = 20) -> list[Transaction]:
    """Generate a realistic mix of test transactions.

    Distribution:
        ~60% normal / low-risk
        ~25% medium-risk
        ~15% high-risk
    """
    transactions: list[Transaction] = []

    for _ in range(count):
        roll = random.random()
        if roll < 0.60:
            transactions.append(_normal_transaction())
        elif roll < 0.85:
            transactions.append(_medium_risk_transaction())
        else:
            transactions.append(_high_risk_transaction())

    return transactions


def generate_single_transaction(**overrides) -> Transaction:
    """Create one baseline transaction with optional field overrides.

    Useful for manual testing — pass any Transaction field as a keyword
    argument to override the default value.

    Example::

        txn = generate_single_transaction(
            amount=500_000_000,
            is_night_transaction=True,
            recipient_type=RecipientType.NEW,
        )
    """
    base = _daytime_ts(_recent_base())
    defaults: dict = dict(
        transaction_id=_txn_id(base),
        transaction_type=TransactionType.DOMESTIC_TRANSFER,
        amount=5_000_000.0,
        currency="IDR",
        timestamp=base,
        sender_account_id="ACC-ID-000001",
        sender_account_age_days=730,
        recipient_account_id="RCP-ID-000001",
        recipient_type=RecipientType.EXISTING,
        recipient_country="ID",
        device_id=DEVICE_IDS[0],
        ip_address=_random_ip(),
        is_night_transaction=False,
        sim_changed_recently=False,
        is_new_device=False,
        memo="Test transaction",
        avg_monthly_txn_count=10,
        avg_transaction_amount=5_000_000.0,
        usual_transaction_hours="09:00-18:00",
        recent_alerts_30d=0,
        daily_txn_count_today=1,
        daily_amount_today=5_000_000.0,
    )
    defaults.update(overrides)
    return Transaction(**defaults)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    random.seed(42)

    print("=" * 70)
    print("KB Indonesia FDS — Sample Transaction Generator")
    print("=" * 70)

    # Generate a batch and show summary
    batch = generate_transactions(20)
    print(f"\nGenerated {len(batch)} transactions:\n")

    for txn in batch:
        risk_hint = []
        if txn.is_night_transaction:
            risk_hint.append("night")
        if txn.is_new_device:
            risk_hint.append("new-device")
        if txn.sim_changed_recently:
            risk_hint.append("SIM-swap")
        if txn.recipient_type == RecipientType.BLACKLISTED:
            risk_hint.append("BLACKLISTED")
        if txn.recipient_type == RecipientType.NEW:
            risk_hint.append("new-recip")
        if txn.recipient_country not in ("ID",):
            risk_hint.append(f"country={txn.recipient_country}")

        hint_str = ", ".join(risk_hint) if risk_hint else "clean"
        print(
            f"  {txn.transaction_id}"
            f"  {txn.transaction_type.value:<28}"
            f"  IDR {txn.amount:>16,.0f}"
            f"  [{hint_str}]"
        )

    # Show a manually overridden single transaction
    print("\n" + "=" * 70)
    print("Manual override example (high-risk SIM swap):")
    print("=" * 70)
    manual = generate_single_transaction(
        amount=250_000_000,
        is_night_transaction=True,
        sim_changed_recently=True,
        is_new_device=True,
        recipient_type=RecipientType.NEW,
        sender_account_age_days=45,
        daily_txn_count_today=7,
    )
    print(manual.model_dump_json(indent=2))
