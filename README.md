# 🧬 AI-Driven PCR Melt Curve Analyzer (MVP)

> **⚠️ DEMO ENVIRONMENT – RESEARCH USE ONLY (RUO)** > *Not for diagnostic procedures. This application processes
strictly anonymized data without patient identifiers (PHI) for demonstration and evaluation purposes only.*

## 📌 Project Overview

Standard commercial cycler software often fails to accurately analyze complex multiplex melt curves due to rigid
temperature windows and amplification bias. Overlapping peaks and physical artifacts (e.g., V-shaped baselines)
frequently lead to false interpretations.

This MVP solves this by replacing static thresholds with a dynamic, AI-driven data processing pipeline. It utilizes *
*asymmetric baseline correction (ALS)**, **signal smoothing (Savitzky-Golay)**, **Gaussian peak deconvolution**, and *
*unsupervised Machine Learning (Clustering)** to robustly identify targets based on relative distances rather than
absolute temperatures.

## 🛠️ Core Tech Stack & Principles

* **Backend:** Python 3.14 (Flask)
* **Database Layer:** PostgreSQL via SQLAlchemy 2.1.0b3 (strictly enforcing PEP 750 `t-strings` for SQL injection
  prevention)
* **Math & AI:** NumPy, Pandas, SciPy, Scikit-Learn
* **Architecture:** Strict Separation of Concerns (SoC) & Role-Based Access Control (RBAC)
* **Quality Assurance:** 100% Test-Driven Development (TDD) via `pytest`