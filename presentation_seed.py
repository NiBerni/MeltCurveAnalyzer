import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.db.models import (
    AssayTemplate,
    Base,
    PcrRun,
    Permission,
    Role,
    Sample,
    SampleResult,
    User,
)

# Engine und Session analog zum restlichen Backend initialisieren
engine = create_engine(DATABASE_URL)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def run_seed():
    with SessionLocal() as session:
        print("Starte Datenbank-Seed für die Präsentation...")
        upload_perm = Permission(
            name="upload_runs", description="Darf PCR-Läufe hochladen"
        )
        validate_perm = Permission(
            name="validate_results", description="Darf unklare Ergebnisse validieren"
        )

        # 2. IAM / RBAC: Rollen anlegen und Permissions direkt übergeben
        operator_role = Role(
            name="Operator",
            description="Standard Operator",
            permissions=[upload_perm],  # Nur Upload-Rechte
        )
        senior_role = Role(
            name="Senior",
            description="Darf Eskalationen validieren",
            permissions=[upload_perm, validate_perm],  # Upload + Validate-Rechte
        )
        session.add_all([upload_perm, validate_perm, operator_role, senior_role])

        # 2. IAM / RBAC: User anlegen (MVP plain-text passwort kompatibel)
        operator_user = User(
            username="valid_operator",
            email="operator@labor.local",
            password_hash="correct_password",
            is_active=True,
            roles=[operator_role],
        )
        senior_user = User(
            username="senior_validator",
            email="senior@labor.local",
            password_hash="secure_password",
            is_active=True,
            roles=[senior_role],
        )
        session.add_all([operator_user, senior_user])

        # 3. Assay Template für den sauberen CSV/XML-Upload anlegen
        template = AssayTemplate(
            template_identifier="COVID_MULTIPLEX_v1",
            multiplex_mapping={
                "Mix_1": {
                    "FAM": {
                        "targets": ["SARS-CoV-2", "Flu A"],
                        "expected_tms": [82.5, 78.0],
                    },
                    "HEX": {"targets": ["Internal Control"], "expected_tms": [75.0]},
                }
            },
            description="Demo Template für die MVP Präsentation",
        )
        session.add(template)

        # Flush, um die automatisch generierten UUIDv7 für die Relationen zu erhalten
        session.flush()

        # 4. Historischen Run anlegen (Eskalations-Demo für Senior-Validation)
        run = PcrRun(
            run_identifier="RUN_DEMO_ESCALATION",
            device_id="CYCLER-DEMO-01",
            raw_operator="valid_operator",
            imported_by_id=operator_user.id,
        )
        session.add(run)
        session.flush()

        sample = Sample(pcr_run_id=run.id, well_position="A01")
        session.add(sample)
        session.flush()

        # 5. Result-Entität anlegen, die manuell von einem Senior validiert werden muss
        result = SampleResult(
            sample_id=sample.id,
            target_name="SARS-CoV-2",
            algo_is_positive=True,
            algo_tm_peaks=[82.4, 75.1],  # Simulation eines extrahierten Artefakt-Peaks
            cluster_label="Ambiguous",
            export_status="pending",
        )
        session.add(result)

        # Alles physisch in die Postgres-DB schreiben
        session.commit()

        print("✅ Seed erfolgreich abgeschlossen!")
        print("-" * 50)
        print("📌 Daten für Postman:")
        print(f"1. Login für Upload: valid_operator / correct_password")
        print(f"2. Login für Validation: senior_validator / secure_password")
        print(f"3. Result-ID für '/validate' Endpoint:\n   -> {result.id}")
        print("-" * 50)


if __name__ == "__main__":
    run_seed()
