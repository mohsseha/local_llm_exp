# On-site Evaluation Tool for ChromeBird AI

This repository contains an evaluation tool for ChromeBird AI's deep indexing technology for document processing applications.

&copy; 2025 ChromeBird AI & Husain Al-Mohssen. All rights reserved.

## How to Run

Follow these steps to set up and run the service:

1.  **Create a Project Directory**:
    Create a new, empty folder on your local machine to house the project files.

2.  **Copy Scripts**:
    Copy the following scripts into the directory you just created:
    - `run.chbird.sh`
    - `run.docs2md.sh`

3.  **Add Your Documents**:
    Create a subdirectory named `data` and place all the documents you want to process into this folder.

4.  **Process Documents**:
    Run the document processing script. This will convert your documents into a format that can be indexed.
    ```bash
    ./run.docs2md.sh
    ```

5.  **Start the Service**:
    Run the main application script.
    ```bash
    ./run.chbird.sh
    ```

6.  **Access the Application**:
    Open your web browser and navigate to [http://localhost:8080](http://localhost:8080).