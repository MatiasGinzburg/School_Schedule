# Automated School Scheduler

This repository contains a Python-based scheduling system designed to solve complex school timetabling problems. It parses Excel spreadsheets of professor availability and course requirements, using Integer Linear Programming to generate optimal, conflict-free schedules. The user interface is built with Streamlit for a seamless, browser-based experience.


## Prerequisites 
* Python 3.x
* [uv](https://github.com/astral-sh/uv) (Python package and project manager)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MatiasGinzburg/School_Schedule.git
   cd .\school_schedule\
    ```
2. **Install dependencies:**
Because this project uses uv, you can install all required dependencies (including pandas, openpyxl, pulp, and streamlit) directly from the uv.lock file by running:
    ```bash
    uv sync
     ```

## Usage

3. **Launch the application:**
Start the local Streamlit web server by running the following command in your terminal:
  ```bash
  uv run streamlit run frontend/app.py
  ```

4. **Drag and drop your formatted schedule .xlsx file into the web interface**.

5. **Generate and Download:**
Click Generate Schedule. The application will optimize the schedule to minimize the days professors must attend and compress their active hours. Once verified, you can download both the Master Schedule and the individual Professor Schedules directly from the browser.

## Input Data Format Requirements
Your input Excel (.xlsx) file must contain:

A sheet named exactly hours_per_course containing the course names in the first column, professor names in the first row, and the required teaching hours in the intersecting cells. It must also include schedule metadata in cells T1:U3 detailing the days per week, hours per day, and total hours.

One additional sheet per professor (named exactly as they appear in the hours_per_course sheet) detailing their availability, with days as columns and hours as rows.

A sheet model with an example can be found in the Example_data/school_schedule.xlsx
