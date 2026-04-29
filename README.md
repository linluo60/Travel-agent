# Travel-agent

Travel-agent is a simple web-based travel assistant project. It connects a frontend map page with a Python backend to help users search and view travel-related information in a more interactive way.

## Project Overview

The goal of this project is to build a basic travel assistant that can support trip planning. The frontend provides a map-based user interface, while the backend handles the main logic and API requests.

This project was built as a beginner-friendly full-stack web application. Through this project, I learned how a webpage can communicate with a backend server and how different tools can work together in one project.

## Project Structure

```text
Travel-agent/
├── backend/
│   └── main.py
├── frontend/
│   └── map.html
├── .gitignore
└── README.md
```

## Files

### `frontend/map.html`

This file contains the frontend page of the project. It is responsible for the user interface, including the map display and the user input area.

### `backend/main.py`

This file contains the backend code. It is written in Python and uses FastAPI to handle requests from the frontend.

## Tools Used

- **HTML**: Used to build the frontend webpage.
- **Python**: Used to write the backend logic.
- **FastAPI**: Used to create backend API routes.
- **Uvicorn**: Used to run the FastAPI backend server.
- **GitHub**: Used to store and manage the project code.

## Important Terms

### Frontend

The frontend is the part of the project that users can see and interact with. In this project, `map.html` is the frontend file. It shows the webpage, map, buttons, input boxes, and other visual elements.

### Backend

The backend is the part of the project that runs behind the webpage. It receives requests from the frontend, processes information, and sends results back. In this project, `main.py` is the backend file.

### API

API means Application Programming Interface. In simple words, an API is a way for two programs to communicate with each other. In this project, the frontend sends a request to the backend API, and the backend returns useful travel-related information.

### FastAPI

FastAPI is a Python framework used to build APIs. It makes it easier to create backend routes that the frontend can call.

### Uvicorn

Uvicorn is a server used to run FastAPI applications. It allows the backend code in `main.py` to run locally on a computer.

### GitHub

GitHub is a platform for storing, sharing, and managing code. It also helps track project changes over time.

## How to Run the Project

### 1. Clone the repository

```bash
git clone https://github.com/linluo60/Travel-agent.git
```

### 2. Go into the project folder

```bash
cd Travel-agent
```

### 3. Go into the backend folder

```bash
cd backend
```

### 4. Install required Python packages

If FastAPI and Uvicorn are not installed yet, run:

```bash
pip install fastapi uvicorn
```

### 5. Start the backend server

```bash
uvicorn main:app --reload
```

After running this command, the backend server should start at:

```text
http://127.0.0.1:8000
```

You can also check the automatic API documentation at:

```text
http://127.0.0.1:8000/docs
```

### 6. Open the frontend page

Open the file below in a web browser:

```text
frontend/map.html
```

Then you can interact with the travel-agent webpage.

## Main Functions

This project can:

- Display a map-based frontend page.
- Connect the frontend with a Python backend.
- Receive user input from the webpage.
- Send requests to the backend.
- Return travel-related results through the web interface.

## Current Limitations

This project is still an early version. Some functions may need further improvement, such as better user interaction, more stable API responses, and a more polished interface design.

Currently, the project is mainly designed to run locally. It has not been deployed online yet, so users need to run the backend server on their own computer before using the full project.

## Future Improvements

In the future, I would like to improve this project by:

- Adding more travel recommendation functions.
- Improving the map interface.
- Connecting more real-time travel data, such as weather or location information.
- Making the frontend design cleaner and easier to use.
- Adding error handling for failed API requests.
- Deploying the project online so that others can access it directly.

## Author

Lin Luo
