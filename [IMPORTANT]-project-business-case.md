# Business Case Specification: AGENT P

## 1. Project Overview
* **Project Name:** AGENT P (Predictive & Parametric Solar Analytics Assistant)
* **Project Type:** API-Based Agentic AI System
* **Domain:** Renewable Energy & Cleantech Analytics
* **Core Data Source:** National Renewable Energy Laboratory (NREL) / National Solar Radiation Database (NSRDB) API

---

## 2. Problem Statement
The clean energy transition requires rapid, data-driven feasibility assessments for solar installations. However, solar irradiation data is traditionally locked behind complex climate registries, specialized APIs (NREL/NSRDB), and heavy multi-parameter queries. 

### Current Industry Bottlenecks:
* **High Technical Barrier:** Project developers, solar installers, and sustainability analysts must manually construct rigid API queries specifying exact latitudes, longitudes, system attributes, and year parameters.
* **Data Fragmentation:** Raw solar resource inputs require post-retrieval processing, mathematical aggregation (e.g., converting hourly data into monthly averages), and formatting before becoming actionable.
* **Inflexible Tooling:** Standard software solutions provide fixed dashboards that cannot dynamically handle contextual, time-bounded, or location-relative conversational queries.

---

## 3. Target Audience & Users
AGENT P is designed to democratize access to advanced solar metrics for non-technical stakeholders:
* **Solar Project Developers & Engineers:** Conducting rapid preliminary site surveys and solar yield evaluations.
* **Sustainability & ESG Consultants:** Calculating localized carbon offsets and environmental impacts based on historical irradiance.
* **Commercial Property Owners:** Assessing the regional viability of transitioning facility roofs to solar microgrids.

---

## 4. Why an Agentic Approach is Appropriate
A simple prompt or standard semantic RAG pipeline is insufficient here because the workflow demands **multi-step deterministic reasoning over external APIs** and raw numerical calculation. 

An agentic architecture solves this problem through the following loop:
* **Intent Parsing & Disambiguation:** The agent converts a natural language query (e.g., *"Give me the monthly average irradiation from Feb to June in 2022"*) into structured parameters (Latitude, Longitude, Year, Months, Data attributes).
* **Dynamic Tool Use:** The agent automatically calls the external NREL/NSRDB API endpoint with the parsed query parameters.
* **Data Processing & Analytics:** The agent treats downstream data science/exploratory scripts as accessible tools, summarizing hourly raw data dumps into the requested monthly averages.
* **Contextual Response Generation:** The agent surfaces the calculated findings into a clear conversational response accompanied by downloadable CSV summaries via the Web UI.

---

## 5. Sample Core Workflow Triggers
The application must robustly handle and parse variations of the following core user intent:
> "Give me the monthly average irradiation from Feb to June in 2022 at our warehouse location in Caloocan."