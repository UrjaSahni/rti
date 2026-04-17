"""
Database seeder — creates tables and populates them with:
  1. 13 real government departments with PIO details
  2. 50 synthetic citizens (Faker en_IN)
  3. 300 synthetic RTI applications (Faker en_IN)
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from faker import Faker
from sqlalchemy.orm import Session

from app.database.models import create_tables, SessionLocal, Department, Citizen, RTIApplication

fake = Faker("en_IN")
random.seed(42)

# ─── Department Data ───────────────────────────────────────────────────────────
DEPARTMENTS = [
    {
        "name": "Ministry of Railways",
        "ministry": "Ministry of Railways",
        "pio_name": "Shri Rajesh Kumar, PIO",
        "pio_email": "pio.railways@gov.in",
        "pio_address": "Rail Bhavan, Raisina Road, New Delhi - 110001",
        "appeal_authority_name": "Joint Secretary (RTI), Ministry of Railways",
        "appeal_authority_email": "faa.railways@gov.in",
    },
    {
        "name": "CBSE",
        "ministry": "Ministry of Education",
        "pio_name": "Smt. Priya Sharma, PIO",
        "pio_email": "pio.cbse@gov.in",
        "pio_address": "CBSE Headquarters, 2, Community Centre, Preet Vihar, New Delhi - 110092",
        "appeal_authority_name": "Deputy Secretary (RTI), Ministry of Education",
        "appeal_authority_email": "faa.cbse@gov.in",
    },
    {
        "name": "EPFO",
        "ministry": "Ministry of Labour & Employment",
        "pio_name": "Shri Anil Verma, PIO",
        "pio_email": "pio.epfo@gov.in",
        "pio_address": "EPFO Headquarters, Bhavishya Nidhi Bhawan, 14, Bhikaji Cama Place, New Delhi - 110066",
        "appeal_authority_name": "Regional PF Commissioner (RTI Appellate)",
        "appeal_authority_email": "faa.epfo@gov.in",
    },
    {
        "name": "Delhi Police",
        "ministry": "Ministry of Home Affairs",
        "pio_name": "Inspector Suresh Singh, PIO",
        "pio_email": "pio.delhipolice@gov.in",
        "pio_address": "Delhi Police Headquarters, MSO Building, ITO, New Delhi - 110002",
        "appeal_authority_name": "DCP (RTI), Delhi Police",
        "appeal_authority_email": "faa.delhipolice@gov.in",
    },
    {
        "name": "Income Tax Dept",
        "ministry": "Ministry of Finance",
        "pio_name": "Shri Vinod Gupta, PIO",
        "pio_email": "pio.incometax@gov.in",
        "pio_address": "Central Board of Direct Taxes, North Block, New Delhi - 110001",
        "appeal_authority_name": "CIT (RTI Appellate), CBDT",
        "appeal_authority_email": "faa.incometax@gov.in",
    },
    {
        "name": "Passport Office",
        "ministry": "Ministry of External Affairs",
        "pio_name": "Smt. Meera Nair, PIO",
        "pio_email": "pio.passport@gov.in",
        "pio_address": "Passport Seva Kendra, Patiala House, New Delhi - 110001",
        "appeal_authority_name": "Regional Passport Officer (Appellate)",
        "appeal_authority_email": "faa.passport@gov.in",
    },
    {
        "name": "AIIMS",
        "ministry": "Ministry of Health & Family Welfare",
        "pio_name": "Dr. K.L. Mehta, PIO",
        "pio_email": "pio.aiims@gov.in",
        "pio_address": "AIIMS, Ansari Nagar, New Delhi - 110029",
        "appeal_authority_name": "Medical Superintendent (RTI Appellate), AIIMS",
        "appeal_authority_email": "faa.aiims@gov.in",
    },
    {
        "name": "DDA",
        "ministry": "Ministry of Housing & Urban Affairs",
        "pio_name": "Shri Rakesh Tyagi, PIO",
        "pio_email": "pio.dda@gov.in",
        "pio_address": "DDA Headquarters, Vikas Sadan, INA, New Delhi - 110023",
        "appeal_authority_name": "Director (RTI Appellate), DDA",
        "appeal_authority_email": "faa.dda@gov.in",
    },
    {
        "name": "RBI",
        "ministry": "Ministry of Finance",
        "pio_name": "Shri P.R. Iyer, PIO",
        "pio_email": "pio.rbi@rbi.org.in",
        "pio_address": "Reserve Bank of India, Central Office, Shahid Bhagat Singh Road, Mumbai - 400001",
        "appeal_authority_name": "Chief General Manager (RTI Appellate), RBI",
        "appeal_authority_email": "faa.rbi@rbi.org.in",
    },
    {
        "name": "SEBI",
        "ministry": "Ministry of Finance",
        "pio_name": "Smt. Deepa Menon, PIO",
        "pio_email": "pio.sebi@sebi.gov.in",
        "pio_address": "SEBI Bhavan, Plot No. C4-A, G Block, Bandra Kurla Complex, Mumbai - 400051",
        "appeal_authority_name": "Executive Director (RTI Appellate), SEBI",
        "appeal_authority_email": "faa.sebi@sebi.gov.in",
    },
    {
        "name": "MCD",
        "ministry": "Ministry of Housing & Urban Affairs",
        "pio_name": "Shri Mahesh Chauhan, PIO",
        "pio_email": "pio.mcd@gov.in",
        "pio_address": "MCD Headquarters, Dr. S.P. Mukherjee Civic Centre, New Delhi - 110002",
        "appeal_authority_name": "Additional Commissioner (RTI Appellate), MCD",
        "appeal_authority_email": "faa.mcd@gov.in",
    },
    {
        "name": "BSNL",
        "ministry": "Ministry of Communications",
        "pio_name": "Shri V.K. Saxena, PIO",
        "pio_email": "pio.bsnl@bsnl.co.in",
        "pio_address": "BSNL Corporate Office, Statesman House, 148, Barakhamba Road, New Delhi - 110001",
        "appeal_authority_name": "General Manager (RTI Appellate), BSNL",
        "appeal_authority_email": "faa.bsnl@bsnl.co.in",
    },
    {
        "name": "LIC of India",
        "ministry": "Ministry of Finance",
        "pio_name": "Smt. Sunita Patil, PIO",
        "pio_email": "pio.lic@licindia.in",
        "pio_address": "LIC of India, Central Office, Yogakshema, Jeevan Bima Marg, Mumbai - 400021",
        "appeal_authority_name": "Executive Director (RTI Appellate), LIC",
        "appeal_authority_email": "faa.lic@licindia.in",
    },
]

STATUSES = ["PENDING", "SUBMITTED", "RESPONDED", "APPEALED", "RESOLVED", "OVERDUE"]
STATUS_WEIGHTS = [0.10, 0.30, 0.30, 0.20, 0.10, 0.00]  # mapped to spec's 40/30/20/10

# Spec status mapping (for the applications CSV semantics)
STATUS_POOL = (
    ["SUBMITTED"] * 40
    + ["RESPONDED"] * 30
    + ["APPEALED"] * 20
    + ["RESOLVED"] * 10
)


def seed_departments(db: Session):
    """Insert all 13 department records if they don't already exist."""
    for d in DEPARTMENTS:
        existing = db.query(Department).filter(Department.name == d["name"]).first()
        if not existing:
            dept = Department(**d)
            db.add(dept)
    db.commit()
    print(f"[seed] Departments seeded: {len(DEPARTMENTS)}")


def seed_citizens(db: Session, count: int = 50):
    """Generate and insert synthetic citizen records using Faker."""
    created = 0
    for _ in range(count):
        email = fake.unique.email()
        citizen = Citizen(
            name=fake.name(),
            email=email,
            phone=fake.phone_number()[:15],
            address=fake.address().replace("\n", ", "),
        )
        db.add(citizen)
        created += 1
    db.commit()
    print(f"[seed] Citizens seeded: {created}")


def seed_applications(db: Session, count: int = 300):
    """Generate and insert synthetic RTI applications using Faker."""
    citizens = db.query(Citizen).all()
    departments = db.query(Department).all()

    if not citizens or not departments:
        print("[seed] ERROR: Seed citizens and departments first.")
        return

    RTI_SUBJECTS = [
        "Status of pending grievance application",
        "Details of recruitment process",
        "Information about pension payment",
        "Details of public funds utilization",
        "Copies of inspection reports",
        "Status of complaint filed",
        "List of beneficiaries under scheme",
        "Details of tender awarded",
        "Information on property records",
        "Status of visa/passport application",
        "Details of road construction tender",
        "Information on ration card status",
        "Details of school admission process",
        "Status of medical reimbursement claim",
        "Information on water supply project",
    ]

    created = 0
    for i in range(count):
        citizen = random.choice(citizens)
        dept = random.choice(departments)
        status = random.choice(STATUS_POOL)

        days_back = random.randint(1, 180)
        filed_date = date.today() - timedelta(days=days_back)
        deadline = filed_date + timedelta(days=30)
        is_overdue = date.today() > deadline and status not in ("RESPONDED", "RESOLVED")
        if is_overdue and status == "SUBMITTED":
            status = "OVERDUE"

        year = filed_date.year
        seq = 10000 + i
        app_number = f"RTI/{year}/{seq:05d}"

        subject = random.choice(RTI_SUBJECTS)
        info_req = f"Please provide {subject.lower()} for department {dept.name}."

        app = RTIApplication(
            application_number=app_number,
            citizen_id=citizen.id,
            department_id=dept.id,
            subject=subject,
            information_requested=info_req,
            date_filed=filed_date,
            deadline_date=deadline,
            status=status,
            priority=random.choice(["NORMAL", "NORMAL", "NORMAL", "LIFE_LIBERTY"]),
            fee_paid=random.choice([True, True, True, False]),
            fee_amount=random.choice([0.0, 10.0, 10.0]),
            bpl_exemption=random.choice([False, False, False, True]),
            draft_text=f"Formal RTI application regarding: {subject}",
        )
        db.add(app)
        created += 1

    db.commit()
    print(f"[seed] RTI Applications seeded: {created}")


def run_seed():
    """Run the full database seeding pipeline."""
    print("[seed] Creating database tables...")
    create_tables()

    db = SessionLocal()
    try:
        print("[seed] Seeding departments...")
        seed_departments(db)

        print("[seed] Seeding citizens...")
        seed_citizens(db, count=50)

        print("[seed] Seeding RTI applications...")
        seed_applications(db, count=300)

        print("\n[seed] Database seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
