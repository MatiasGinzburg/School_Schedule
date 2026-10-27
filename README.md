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

5. **Choose optimization objectives**:
On the left-side panel you will find a dropdown menu from wich you can select the objectives that you want to optimize. 

6. **Visualisation and manual editing:**
Visualize and manually edit the schedule for fine tuning.

7. **Generate and Download:**
Click Generate Schedule. The application will optimize the schedule to minimize the days professors must attend and compress their active hours. Once verified, you can download both the Master Schedule and the individual Professor Schedules directly from the browser.

## Input Data Format Requirements
The application requires a single, consolidated .xlsx workbook containing specific master sheets to define the schedule.

Your input Excel file must contain the following specific tabs:

**Names** Sheet:

Contains the canonical lists used to build the schedule.

Must have columns titled Courses, Professors, Subjects, Days, and Hours.

The first data row is reserved for item counts, and the actual names must be listed from the second row downwards.

**Courses_disponibility** Sheet:

Defines the tri-state availability for the student groups.

The first 5 rows are reserved for notes and are ignored by the parser. Row 6 must contain the column headers (Days/Hours), and Column A must list the course names.

Valid Inputs: 0 (course is not at school), 1 (mandatory slot, requiring exactly one professor), or 2 (optional/flexible slot, where unassigned hours are automatically grouped at the end of the day).

**Professors_disponibility** Sheet:

Defines when professors are available to work.

Follows the same structure as the courses sheet: the first 5 rows are ignored, Row 6 contains headers, and Column A lists the professor names.

Valid Inputs: 1 (available to teach) or 0 (unavailable).

**Subjects** Sheet:

Assign to each subject the total amount of hours, the professors and the courses.

First row is ignored, second row contains the headers.

The professors and courses assigned to a same subject must be placed at the same time slot.

**Example data**

*A sheet model with an example can be found in Example_data/Horarios_SG.xlsx.*
