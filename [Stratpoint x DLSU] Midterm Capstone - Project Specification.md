Introduction to Agentic AI (STAI100)

**Midterm Capstone**

Project Specification

Due: Week 9  ·  Teams of 3–4 students

# **1\. Overview**

The Midterm Capstone is the first major integration milestone of the course. Over Weeks 1–7, you have built individual components of an agentic AI system; prompt engineering, structured outputs, retrieval-augmented generation (RAG), memory, guardrails, tool use, and agent loops. The Midterm Capstone asks you to bring these components together into a single, coherent, working application grounded in a real business problem.

Your team will design, build, evaluate, and present an end-to-end agentic system. The deliverable is not a prototype or a demo script; it is a deployable application with documented architecture, observable behavior, and evidence of systematic testing.

| What you will build A working agentic AI application solving a real business problem Integrating modules from Weeks 1–7 (at least 2 modules per team member) Accessible via a web UI and an API endpoint Deployed with basic LLMOps monitoring Documented with a technical write-up (≥2,000 words) and a clean code repository |
| :---- |

# **2\. Learning Objectives**

By completing this capstone, students will be able to:

* Integrate multiple agentic components (RAG, memory, guardrails, tool use) into a single coherent system

* Justify architectural decisions and communicate trade-offs clearly

* Evaluate system reliability through structured experiments and document findings

* Package and deploy an AI application with observability tooling

* Present technical work to a non-specialist audience using a business framing

# **3\. Project Requirements**

## **3.1  Technical Requirements**

* Working, end-to-end agentic AI application

* Demonstrates modules from Weeks 1–7; minimum 2 modules per team member (e.g., a 3-person team covers at least 6 modules)

* Accessible via a web UI (e.g., Streamlit, Gradio)

* Exposes an API endpoint (REST)

* Deployed with basic LLMOps monitoring (e.g. MLFlow) 

* Containerized with a Dockerfile and documented build/run instructions

## **3.2  Team Requirements**

* Teams of 3–4 students; self-formed by Week 6

* Each member must own and be able to explain at least 2 modules

* All members participate in the live presentation

## **3.3  Deliverables**

Submit all of the following by the Week 9 deadline:

| Deliverable | Details |
| :---- | :---- |
| **Live Presentation** | 10–15 minutes including Q\&A; slides required |
| **Technical Write-up** | ≥2,000 words covering business case, methodology, architecture, experiments, and retrospective |
| **Source Code Repository** | GitHub (or equivalent .zip) repo with README, Dockerfile, and inline documentation |
| **Working Demo** | Live, accessible demo during presentation (no pre-recorded video substitutes) |

# **4\. Module Checklist**

Each team member is responsible for at least two modules from the list below. During the presentation, every member should be prepared to walk through the modules they owned; explaining design decisions, showing relevant code, and discussing evaluation results.

| Module | Description |
| :---- | :---- |
| **Prompt Engineering** | Design and iterate on system prompts; apply few-shot, chain-of-thought, and structured prompt patterns |
| **Structured Outputs** | Return typed, schema-validated responses (JSON, Pydantic, etc.) for downstream consumption |
| **Disambiguation** | Detect ambiguous inputs and clarify intent before proceeding with tool calls or generation |
| **RAG** | Retrieve relevant context from a vector, SQL, or graph store and ground model responses in retrieved data |
| **Memory** | Maintain short-term session memory and/or long-term persistent memory across conversations |
| **Guardrails** | Implement input/output validation, topic filtering, and safety checks |
| **ReAct Agent** | Implement a reasoning \+ acting loop where the model plans and executes steps iteratively |
| **SQL Agent** | Generate and execute SQL queries against a relational database based on natural language |
| **Tool Use** | Integrate at least one external tool or API (search, weather, calendar, etc.) |
| **Chat UI** | Build a functional conversational interface (e.g., Streamlit, Gradio) |
| **API Endpoint** | Expose the agent via a REST API endpoint |
| **LLMOps Monitoring** | Log traces, latency, token usage, and errors using an observability tool (e.g., MLFlow) |
| **Dockerization** | Package the application in a Dockerfile with documented build and run instructions |

Note: Prompt Engineering is foundational and expected to appear throughout the system. It counts as a module only when it is explicitly designed, iterated on, and evaluated (e.g., ablation across prompt variants).

# **5\. Presentation Structure**

Presentations are 15-20 minutes followed by Q\&A.   
(5 mins per person, i.e. 15 mins for 3-person team)

Structure your slides around the following sections:

| \# | Section | What to Cover |
| :---- | :---- | :---- |
| 1 | **Business Use Case** | The problem, the target user, and why an agentic approach is appropriate |
| 2 | **Architecture & Methodology** | System diagram, component breakdown, data model and flow, and technology stack |
| 3 | **Live Demo** | Walkthrough of the working application; demonstrate key agentic behaviors |
| 4 | **Experiment Findings** | What you tested, how you measured it, and what the results showed |
| 5 | **Retrospective** | What worked, what did not, what you would do differently, and open issues |

# **6\. Grading Rubric**

| Criterion | Weight | Description |
| :---- | :---- | :---- |
| **Technical Depth and Correctness** | 30% | Correct use of RAG, memory, guardrails, tool use, and agent patterns; architecture matches implementation |
| **System Architecture and Design Quality** | 25% | Clear separation of concerns, appropriate component selection, coherent data flow |
| **Eval Results and Reliability Demonstration** | 20% | Evidence-based testing, edge case handling, documented failure modes and mitigations |
| **Presentation Quality and Live Demo** | 15% | Clear communication of business case, smooth walkthrough, answers to Q\&A |
| **Code Quality, Documentation, and README** | 10% | Readable code, inline comments, complete README with setup instructions and architecture overview |

Note: A functional live demo is expected. A demo that fails to run during presentation will affect the “Presentation Quality and Live Demo” criterion. Prepare a fallback (e.g., screen recording) and disclose it upfront.

# **7\. Course Grading Context**

The Midterm Capstone contributes 30% of your final course grade. The table below shows how all assessments are weighted.

| Assessment | Weight | Description |
| :---- | :---- | :---- |
| **Weekly Homework** | 25% | Lab exercises submitted as Jupyter notebooks with documentation |
| **Midterm Capstone (Week 9\)** | 30% | Working agentic system demonstrating components from Weeks 1 to 7 |
| **Final Capstone Project (Week 14\)** | 40% | End-to-end agentic solution with CV/DS model integration |
| **Participation & Peer Review** | 5% | In-class engagement, capstone dry-run feedback, Week 14 peer evaluations |

# **8\. Choosing a Good Problem**

Not every problem benefits from an agentic approach. Use the criteria below to evaluate your proposed use case before committing.

| ✅  Good Fits for Agentic AI Multi-step reasoning over external tools or APIs Processes unstructured data (PDFs, audio, images, web pages) Needs memory or context across a conversation Real users with measurable success criteria Workflow currently done manually and repeatedly | ❌  Poor Fits for Agentic AI Single-call Q\&A ;  a well-crafted prompt would suffice Pure CRUD apps using an LLM as a thin wrapper Tasks where deterministic code already wins Problems with no ground truth or evaluation framework Safety-critical workflows without a human-in-the-loop |
| :---- | :---- |

# **9\. Suggested Use Cases**

The table below lists suggested use cases organized by retrieval type (API, SQL, Vector DB, Graph DB). These are starting points; you are encouraged to propose your own problem, as long as it meets the criteria in Section 8\. Teams building toward the Final Capstone may also want to consider use cases that can later incorporate a CV or DS model.

Refer to the sheet provided in-class for the updated list, and to note down the use case that your group will be taking.

| RAG Type | Use Case | Example Query |
| :---- | :---- | :---- |
| **API** | Weather / Climate Data | "Give me the months where rainfall exceeded 150 mm in 2023." |
|  | Solar Irradiation (NREL/NSRDB) | "What is the monthly average irradiation from Feb to June 2022?" |
|  | Stock Price Monitoring | "What were the min/max prices of $GLO (Globe Telecom) from May to June?" |
|  | Valuation Modeling | "What is the current DCF-based valuation of $COMPANY?" |
|  | SEC / Tax Filing Research | "Retrieve all relevant tax filings and registration documents for \<Company\>." |
|  | HR Scheduling | "From the top 20 candidates, send email invites to the 5 we haven't interviewed yet." |
| **SQL** | Virtual Finance Analyst | "List the top 5 departments with highest operational expenses last quarter." |
|  | Company L\&D Training Tracker | "What mandatory trainings do I need to complete for the Cloud & Data capability?" |
|  | Supply Chain / Inventory | "Show the top 10 SKUs with the highest lead times this month." |
|  | Customer Segmentation | "How many segments should I create ad campaigns for based on 2025 data?" |
|  | Hospital Directory | "Which cardiologists are available on Tuesdays and accredited with MediCard?" |
| **Vector DB** | Healthcare Procedures Q\&A | "I have a lipid profile test at 10 AM ;  what time should I last eat?" |
|  | Medical Pricing | "How much is a CT scan, and what portion is covered by PhilHealth?" |
|  | Junior QA Assistant | "Generate a test plan for a virtual assistant built for a car dealership." |
|  | Digital Trends Research | "Which social media platform should we focus on for maximum reach in PH 2026?" |
|  | Website Q\&A (External) | "What Stratpoint projects were related to retail?" |
|  | HR Onboarding | "What do I need to do on my first day?" |
|  | Legal / IP Assistant | "What are the penalties for intellectual property fraud?" |
|  | Style Guide Checker | "Review this PR against the Google Style Guide." |
| **Graph DB** | Address Resolution | "Which cities fall under the NCR region?" |
|  | Disease Propagation | "If Quezon City is locked down, which neighboring cities are at risk?" |
|  | HR Org Chart / Mentorship | "Who is my tech mentor, and who is my career mentor?" |
|  | Recommendation Engine | "Which movies are similar to Movie X based on user ratings?" |

# **10\. Path to the Final Capstone (Optional)**

The Final Capstone (Week 14, 40% of course grade) extends your Midterm Capstone with a Computer Vision or Data Science model integration. Building on your Midterm project is encouraged but not required; teams may start fresh for the Final.

If you plan to build on this project, consider selecting a use case and architecture that leaves room for model integration. For example:

* A supply chain agent (Midterm) that incorporates a demand forecasting model (Final)

* A hospital triage assistant (Midterm) that adds medical image analysis (Final)

* A customer segmentation tool (Midterm) that plugs in a classification or clustering model (Final)

| 📷  Computer Vision Track Object detection and OCR pipelines Multimodal agents (image \+ text) Document understanding (forms, receipts) Example: LLM \+ CV for license plate retrieval, object detection timestamps | 📊  Data Science Track RAG-driven NLP pipelines Analytics and report automation Tool-using research agents Example: LLM \+ DS for forecasting, segmentation, or financial modeling |
| :---- | :---- |

Discuss your Final Capstone direction with your instructor during or after the Midterm presentation if you want early feedback.

# **11\. Submission Checklist**

Before submitting, confirm that your team has completed all of the following:

| ✓ | Item |
| :---- | :---- |
| □ | Working demo accessible via web UI and API endpoint |
| □ | At least 2 modules per team member integrated and demonstrable |
| □ | LLMOps monitoring configured (traces, latency, token usage visible) |
| □ | Dockerfile builds and runs cleanly with a single command |
| □ | README includes: project overview, setup instructions, architecture diagram, and module ownership table |
| □ | Technical write-up (≥2,000 words) submitted as PDF or markdown |
| □ | Presentation slides finalized and submitted |
| □ | All team members prepared to answer questions on their owned modules |





CONFIGURING LOCAL SSH ACCESS

PREPARED BY: KMD KALAW

Configuring Local SSH Access to
Provisioned Linux Containers

Prepared by:

Kristine Kalaw
Department of Software Technology
College of Computer Studies
De La Salle University

This  guide  outlines  the  process  of  creating  a  Linux  user  account  within  a  Proxmox-hosted  Linux
container  to  enable  local  SSH  access.  It  assumes that the required Proxmox credentials and target
container information have already been provided.

●  Proxmox is an open-source virtualization platform used to manage virtual machines and Linux

containers on a centralized infrastructure.

●  Linux container (LXC) is a lightweight, isolated operating system environment that shares the

host system's kernel while maintaining its own users, processes, and file system.

●  Secure  Shell  (SSH)  is  a  network  protocol  that  enables  secure  remote  access  to  a  Linux

system through a command-line interface.

○

In this guide, local SSH access refers to connecting directly to a Linux container from a
user's  local  machine  using  an  SSH  client,  allowing  the  user  to  securely  access  and
manage  the  container  through  the  command  line  without  using  the  Proxmox  web
interface console.

Log in to Proxmox

1.  Go to https://ccscloud.dlsu.edu.ph/
○  Click proceed/continue when

prompted

2.  Fill in the appropriate fields with your

provisioned credentials:

○  Proxmox Username
○  Proxmox Password
○  Proxmox Realm

3.  Click Login.

4.  When the “No valid subscription” dialog appears, click OK to ignore it.

v0.1.0

1

CONFIGURING LOCAL SSH ACCESS

PREPARED BY: KMD KALAW

View Linux Container Information

In the top-right corner, you should see the dropdown menu toggle for account-related settings.

On the left sidebar, you’ll see the different nodes within CCS Cloud. If you click the Proxmox Node,
you  should  see  your  LXC  ID  and  LXC  Name  (e.g.,  mayari  and  11553  (STAI10018-server)  in  the
screenshot).

Clicking  the  container  will  display  its  summary  information  in  the  center  pane.  Newly created Linux
containers are powered off by default, so the container status will initially appear as stopped. At the
top of the center pane, you should see the Start and Shutdown container buttons.

Creating a New Linux User

Local SSH access is not permitted using the provided root account. To enable SSH access, create a
new  Linux  user  account  through  the  Proxmox  web  interface  console.  If  the  Linux  container  is  not
already running, start it first before proceeding with the user creation steps.

v0.1.0

2

CONFIGURING LOCAL SSH ACCESS

PREPARED BY: KMD KALAW

1.  Open the Console. The Console button in the top bar opens a new pop-out window, while the
Console  tab  in  the  center  pane  (below  the  Summary  tab)  opens the console within the main
interface.

2.  Input  the  LCX  credentials.  Note  that  all  the  password  prompts  will  not  display  any  visual

feedback while you type or paste the password.

Ubuntu 22.04 LTS STAI10018-Server tty1

STAI10018-Server login: LCX_Root_Username
Password: LCX_Root_Password

3.  On successful login, you should see the Ubuntu welcome message.

Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.8.12-18-pve x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

The programs included with the Ubuntu system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Ubuntu comes with ABSOLUTELY NO WARRANTY, to the extent permitted by
applicable law.

root@STAI10018-Server:~#

4.  Create a new Linux user by running adduser your_new_username. You will be prompted to
set  a  password  for  the  new  account.  Afterward,  the  system  will  request  additional  user
information, which can be left blank.

root@STAI10018-Server:~# adduser kmdk
Adding user `kmdk' ...
Adding new group `kmdk' (1000) ...
Adding new user `kmdk' (1000) with group `kmdk' ...
Creating home directory `/home/kmdk' ...
Copying files from `/etc/skel' ...
New password: Non_Root_Password
Retype new password: Non_Root_Password
passwd: password updated successfully
Changing the user information for kmdk
Enter the new value, or press ENTER for the default

v0.1.0

3

CONFIGURING LOCAL SSH ACCESS

PREPARED BY: KMD KALAW

        Full Name []:
        Room Number []:
        Work Phone []:
        Home Phone []:
        Other []:
Is the information correct? [Y/n] Y

5.  Grant  sudo  privileges

to

the  new  account  by

running  usermod  -aG  sudo

your_new_username

root@STAI10018-Server:~# usermod -aG sudo kmdk

6.  Run exit to log out of the current session. Then, log back in using the new user credentials to
confirm  that  the  account  was  created  successfully.  Note  the  change  in  the  console  prompt,
which indicates you are now logged in as the new user rather than root.

root@STAI10018-Server:~# exit
logout

Ubuntu 22.04 LTS STAI10018-Server tty1

STAI10018-Server login: kmdk
Password: Non_Root_Password
Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.8.12-18-pve x86_64)
  [...]

kmdk@STAI10018-Server:~$

Creating a New Linux User

You can begin deploying applications in the Linux container using the Proxmox web interface console.
If  you  prefer  to  work  without  logging  into Proxmox, you can configure local SSH access instead. To
know if your terminal has an SSH client installed, run ssh -V

1.  In your local terminal, run the following command:

○  ssh -p External_Port_22 Non_Root_Username@Public_IP_Address

~>$ ssh -p 2137 kmdk@103.231.240.130

2.  On initial SSH connection, you will be prompted to confirm the host key. Enter yes to proceed.
You  will  then  be  prompted  for  the  password.  A  successful  login  will  display  the  Ubuntu
welcome  message.  Note  the  change  in  the  console  prompt,  which  shows  that  you  are  now
logged in via SSH from your local machine and working directly in the Linux container.

~>$ ssh -p 2137 kmdk@103.231.240.130
The authenticity of host '[103.231.240.130]:2137 ([103.231.240.130]:2137)'

v0.1.0

4

CONFIGURING LOCAL SSH ACCESS

PREPARED BY: KMD KALAW

can't be established.
ED25519 key fingerprint is [REDACTED].
This key is not known by any other names
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '[103.231.240.130]:2137' (ED25519) to the list of
known hosts.
kmdk@103.231.240.130's password: Non_Root_Password
Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.8.12-18-pve x86_64)
  [...]

kmdk@STAI10018-Server:~$

3.  Close  the  SSH  connection  by  running  exit.  Note  the  switch  back  to  the  console  prompt,

which indicates you are no longer connected via SSH.

kmdk@STAI10018-Server:~$ exit
logout
Connection to 103.231.240.130 closed.

~>$

4.  Subsequent SSH connections will only prompt for the password.

~>$ ssh -p 2137 kmdk@103.231.240.130
kmdk@103.231.240.130's password: Non_Root_Password
Welcome to Ubuntu 22.04 LTS (GNU/Linux 6.8.12-18-pve x86_64)
  [...]

kmdk@STAI10018-Server:~$

Acknowledgments / Disclosure

The following Generative AI tools were used to assist in the making of this document:

●  ChatGPT  was  mainly  used  to  streamline  and/or  construct  sentences. The instructor validated the AI-generated

output and modified it as needed.

v0.1.0

5

SAMPLE IMPLEMENTATION:
```
Segment smarter. Sell faster.
Your Name

I. Background
IV. System Demo
• Context Setting
V. Results and Discussion
• Problem Statement
• Proposed Solution and Target
• Pipeline Evaluation
Users
• Challenges
• Results
II. System Design
• Core Features
VI. Moving Forward
• Data Source
• System Architecture
III. Methodology
• Tech Stack
• Node Configurations

I. INTRODUCTION: Context Setting

I. INTRODUCTION: Context Setting
ONLY
of cold calls translate into
ACTUAL SALES
Lead Forensics, 2026
https://www.leadforensics.com/blog/cold-call/cold-calling-statistics/

I. INTRODUCTION: Context Setting
the process of building interest in
| a  product  | or  service  | and  | then |
| ----------- | ------------ | ---- | ---- |
turning that interest into a sale.
https://www.salesforce.com/ap/marketing/lead-generation-guide/

I. INTRODUCTION: Context Setting
of marketers say of leads never convert to
generating quality leads sales due to poor nurturing
is their top challenge and qualification
Martal Group, 2026
https://martal.ca/lead-generation-statistics-lb/

I. INTRODUCTION
Problem Statement
The problem isn’t generating
leads. It’s generating the right
ones and converting them
effectively.

I. INTRODUCTION: Proposed Solution
An AI Chatbot for natural language
queries on customer segmentation.
A user-friendly tool for sales teams and
marketing analysts.
Businesses using AI for lead generation
report a 50% increase in sales-ready leads
and up to 60% lower customer acquisition
costs
Martal Group, 2026
https://martal.ca/lead-generation-statistics-lb/

I. INTRODUCTION: Proposed Solution
Customer Segmentation Tool
Segmentation ensures we’re
not just generating leads, but
prioritizing the right ones.

II. SYSTEM DESIGN
| Segment        | SQL-RAG Queries | Chat Interface |
| -------------- | --------------- | -------------- |
| Classification |                 | and CSV Export |
Converts  user
| Constrain the LLM |     | Conversational UI |
| ----------------- | --- | ----------------- |
queris to SQL and
| with deterministic |     | and option to |
| ------------------ | --- | ------------- |
retrieves  relevant
| business logic |     | download .csv |
| -------------- | --- | ------------- |
data
| and predefined |     | results |
| -------------- | --- | ------- |
segments

II. SYSTEM DESIGN: Core Features
RFM Segmentation
R (Recency): How recently a customer
made a purchase.
F (Frequency): How often a customer
makes purchases.
M (Monetary): How much a customer
spends.
Fig. 1: RFM Segmentation Chart
https://lifesight.io/blog/rfm-segmentation/

II. SYSTEM DESIGN
Car Insurance Cold Calls
4000 data entries
19 Features
Primarily intended for classification use
https://www.kaggle.com/datasets/kondla/carins
urance/
Fig. 2: Data Source features summary

II. SYSTEM DESIGN
There are 20 ideal
Ideal Customers?
customers.
USER QUERY LEADGENIE REPLY
SQL Agent
Generate SQL
additional
Classify filters
customer Parse User Intent Check SQL Format Output
segment
identified
action
Predefined
Customer
Execute SQL
Segments
use predefined
parameters
Customer
Database
Fig. 3: High-Level System Pipeline

III. METHODOLOGY
EVALUATION
FRAMEWORK
FRONT-END
LLM
AI AGENT
Fig. 4: Tech Stack

III. METHODOLOGY
Fig. 5: PREDEFINED_SEGMENTS dictionary snippet

III. METHODOLOGY: Node Configurations
Segment Classification
Fig. 3: High-Level System Pipeline
| Literal Match | Semantic Match | Hybrid Match |
| ------------- | -------------- | ------------ |
Description: check if Description: ask LLM to Description: Literal first,
| keywords exist in user | identify keywords in | then Semantic |
| ---------------------- | -------------------- | ------------- |
| query                  | query                |               |
Technique: fuzzy
| Technique: fuzzy | Technique: LLM prompt | matching + LLM prompt |
| ---------------- | --------------------- | --------------------- |
| matching         | engineering           | engineering           |

III. METHODOLOGY: Node Configurations
Parsing User Intent
Fig. 3: High-Level System Pipeline
| Clarify Intent |     | Get Filters | Filter Conflicts |
| -------------- | --- | ----------- | ---------------- |
Description: extract Description: extract Description: resolve
ONLY the action to be filters explicitly filter conflict between
| done and the       | mentioned by user (e.g. |     | extracted filters and |
| ------------------ | ----------------------- | --- | --------------------- |
| mentioned customer | Age above 30)           |     | predefined segment    |
| segment            |                         |     | filters               |
Technique: LLM prompt
| Technique: LLM prompt | engineering |     | Technique: custom |
| --------------------- | ----------- | --- | ----------------- |
| engineering           |             |     | Python code       |

III. METHODOLOGY: Node Configurations
SQL Agent
Non-customized Agent
Fig. 3: High-Level System Pipeline
| Generate SQL | Check SQL | Execute SQL |
| ------------ | --------- | ----------- |
Description: generate Description: check SQL Description: execute
| SQL based on         | query before executing | SQL query and        |
| -------------------- | ---------------------- | -------------------- |
| parameters extracted |                        | formulate a response |
| by previous nodes    | Technique: pre-built   | based on results     |
tool
| Technique: pre-built |     | Technique: pre-built |
| -------------------- | --- | -------------------- |
| tool                 |     | tool                 |
https://docs.langchain.com/oss/python/langchain/sql-agent

III. METHODOLOGY: Node Configurations
Output Formatting
Non-customized Agent
Fig. 3: High-Level System Pipeline

| Error Message | Conflict Message | Success Message |
| ------------- | ---------------- | --------------- |
Description: generate Description: generate Description: output
| an error message  | a message stating user | message from SQL     |
| ----------------- | ---------------------- | -------------------- |
|                   | query conflicts with   | agent                |
| Technique: custom | predefined segment     |                      |
| Python code       | filters                | Technique: pre-built |
tool
Technique: pre-built
tool
https://docs.langchain.com/oss/python/langchain/sql-agent

V. RESULTS: Pipeline Evaluation
30 Test Cases across 7 Categories
Categories
Predefined segments (9)
Predefined with conflict (5)
Predefined with additional
tags (5)
Multiple predefined (3)
Custom segments (3)
Imaginary segments (3)
Edge cases (2)
Fig. 6: TEST_CASES snippet

V. RESULTS: Pipeline Evaluation
Classification Accuracy and LLM Accuracy
Test Case
LLM Accuracy: RAGAS
Classification
Scoring
Accuracy
Pass if:
String matching: check if Correct classification
generated segment ID RAGAS_Avg > 0.7
matches expected
segment ID
Fig. 7: RAGAS Metrics and Description

V. RESULTS: Pipeline Evaluation
Fig. 8: Overall Metrics Comparison Across Workflows

V. RESULTS: Pipeline Evaluation
Fig. 9: Summary Table

V. RESULTS: Pipeline Evaluation
Fig. 10: Individual Metrics Comparison Across Workflows

V. RESULTS: Pipeline Evaluation
Fig. 11: Category Performance Heatmap

V. RESULTS: Pipeline Evaluation
Synthesis
| Top Performer | Agent Match |     | Universal |
| ------------- | ----------- | --- | --------- |
Struggles Challenge
| The Exact Match | This was the poorest | Workflows struggled |     |
| --------------- | -------------------- | ------------------- | --- |
workflow is the clear performing workflow.  categorizing custom
| leader across nearly all |                 | and multiple segment |     |
| ------------------------ | --------------- | -------------------- | --- |
| evaluation criteria.     | Discrepancy was | test cases.          |     |
found when I inspected
|     | the results. | Discrepancy was |     |
| --- | ------------ | --------------- | --- |
found when I inspected
the results.

V. RESULTS: Pipeline Evaluation
| EVALUATION | PARSING LLM | PROMPT      |
| ---------- | ----------- | ----------- |
| AMBIGUITY  | RESPONSES   | ENGINEERING |

V. RESULTS: Pipeline Evaluation
Fig. 12: Ambiguous scores for Agent Match

V. RESULTS: Pipeline Evaluation
Fig. 13: Evidence of correct classification

V. RESULTS: Pipeline Evaluation
Fig. 14: Evidence of incorrect RAGAS average

V. RESULTS: Pipeline Evaluation
Solution
Python script to clean existing .json
| Handle NaN          |        |                      | Wrong | Incorrect RAGAS       |          |
| ------------------- | ------ | -------------------- | ----- | --------------------- | -------- |
|                     | Values | Classification       |       |                       | Averages |
| Set to 0 instead.   |        | Recheck segment tags |       | Recheck metric fields |          |
| Recompute average   |        | and evaluate         |       | and recompute         |          |
| and overall metrics |        | accordingly.         |       | accordingly.          |          |
after.

IV. RESULTS: Limits
Use Case Limitations:
Agent is not built to respond with
comprehensive analyses.
Agent identifies only one predefined
segment every query.
Prototype Limitations:
Predefined segment descriptions and
business criteria were generated with AI
just for the purposes of testing.
Test cases were also generated by AI,
and so, they may not be as realistic as
possible.

VI. Moving Forward
Make testing more robust by diversifying
test cases and testing for reproducibilty.
Utilize SQL metrics for RAGAS instead of
RAG.
Experiment with customized SQL agent
and tools, instead of pre-built.
Integrate additional agents for multi-
workflow systems, enhancing lead
generation capability.
Add feedback loop to improve model
recommendations.

Gabby Resano

V. RESULTS: Pipeline Evaluation
Fig. 12: NaN values in RAGAS metrics

APPENDIX: Challenges
Fig. 14: Debugging incorrect LLM response formats

APPENDIX: Challenges
Sometimes the agent would hallucinate.
My solution was to be very specific and detailed with prompts
Fig. 15: Sample prompt for intent parser node
```



```
This is an exceptionally clean extract. The structural breakdown gives us exactly what we need to map this into a clean production architecture.

Looking at your extracted codebase, there are a few architectural quirks here that work fine in a lab notebook context but will bottleneck you in production—specifically, **redundant PDF parsing on startup**, **inconsistent message history usage**, and **placing core orchestration directly inside the telemetry/middleware file**.

Based on this extraction, here is your modular production-ready refactor map. We will map this structure exactly to the guidelines in the **`[Stratpoint x DLSU] Midterm Capstone - Project Specification.md`** file, which explicitly requires a containerized application, exposed API endpoints, a web UI, and basic LLMOps monitoring.

---

## The Production Target Architecture Map

Instead of keeping everything tightly coupled, we are shifting the codebase into distinct layers: **Config**, **Engine (Core Logic)**, **Services (API & UI)**, and **Telemetry**.

```text
my_capstone_project/
│
├── config/                  
│   ├── settings.py          # Port ENV variables (OLLAMA_BASE_URL, EMBED_MODEL, etc.)
│   └── prompts.py           # SYSTEM_PROMPT strings decoupled from logic
│
├── src/                     
│   ├── __init__.py
│   ├── database.py          # ChromaDB client instances & Ingestion pipelines
│   ├── guardrails.py        # Input/Output validation functions
│   ├── memory.py            # StudentMemory class isolation
│   └── agent.py             # Core Orchestrator (FAQBot execution loop)
│
├── api/                     
│   └── main.py              # FastAPI server, endpoints, and startup lifespan events
│
├── app/                     
│   └── ui.py                # Streamlit interface consuming the FastAPI endpoint
│
└── utils/
    └── telemetry.py         # MLflow span definitions and structured logging

```

---

## File-by-File Migration & Refactoring Strategy

### 1. `config/prompts.py` & `config/settings.py`

* **What goes here:** Extract `SYSTEM_PROMPT` out of `core.py`. Define environment variables with fallbacks using standard Python libraries or `pydantic-settings`.
* **Production Refactor:** Keeping prompts separate allows you to run prompt ablation experiments (crucial for the *Prompt Engineering* module checklist item) without modifying core application code.



### 2. `src/database.py` (Data Storage & Ingestion Layer)

* **What goes here:** Migrate `_embeddings_model`, `_vectorstore`, `ingest_pdf()`, and `rag_retrieve()`.
* **Production Refactor:** Fix the startup bug. In the current setup, `load_handbook()` checks if the vector store is empty on *every* single UI session or API reload. In production, run `ingest_pdf` as a standalone one-time setup script during the Docker build process so the vector database is completely baked into the container image, saving critical runtime compute.

### 3. `src/guardrails.py` & `src/memory.py`

* **What goes here:** Split out all security validations (`is_integrity_violation`, `redact_pii`, `is_on_topic`) and memory classes (`StudentMemory`).
* **Production Refactor:** Isolate these into distinct components so they can be individually assigned to your team members as part of the team module ownership requirements (e.g., Person A owns Guardrails, Person B owns Memory).



### 4. `src/agent.py` (Core Execution Loop)

* **What goes here:** The main orchestration logic of `FAQBot.chat_traced()`.
* **Production Refactor:** Fix the middleware visibility bug. The current `logging_middleware.py -> traced_chat()` function strips conversation history out of `build_messages()`. Resolve this discrepancy here by ensuring the agent orchestrator cleanly handles both RAG context *and* structural memory retrieval uniformly before rendering text.

### 5. `utils/telemetry.py` (LLMOps Monitoring Layer)

* **What goes here:** The MLflow span logic currently residing in `logging_middleware.py`.
* **Production Refactor:** Instead of cluttering the application flow with nested `with mlflow.start_span(...)` blocks, refactor these into clean Python **decorators** (e.g., `@trace_span("rag_retrieval")`) that you can neatly attach to functions in `src/database.py` and `src/agent.py`. This separates your monitoring logic cleanly from execution.

### 6. `api/main.py` & `app/ui.py` (Service Layer)

* **What goes here:** The contents of `app.py` and `frontend.py`.
* **Production Refactor:** Decouple the UI completely. The Streamlit script should *never* import `core.py` or hit the database directly. It must strictly act as a client making HTTP requests to the FastAPI backend endpoints. This satisfies the architecture checklist requiring a functional web UI and an independent REST API endpoint.



---

## Recommended Next Steps with Claude Code

To build out this pipeline without blowing past token limits, execute the following prompt sequences in separate Claude Code steps:

1. **Step 1:** *"Based on the target folder layout provided, create `config/settings.py`, `config/prompts.py`, and `src/database.py` by refactoring the ingestion and retrieval logic from the core snippet."*
2. **Step 2 (After Step 1 completes):** *"Now create `src/guardrails.py` and `src/memory.py` based on the validation and student memory logic found in the core profile."*
3. **Step 3:** *"Create `src/agent.py` to orchestrate the clean input, retrieval, text generation, and history updating, using custom telemetry decorators."*

Would you like to start by generating the specific `src/database.py` component file first?
```