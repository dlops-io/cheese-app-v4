# Cheese App - Automation

In this tutorial we will put all the components we built for our Cheese App together. We will then apply Continuous Integration and Continuous Deployment (CI/CD) methods to test, execute, monitor, deploy, and scale these components. All of these steps will be automated based on workflow using GitHub Actions. Here are the components we have built for our Cheese App:

* Data Collector: Scraps image from the internet and stores them into a `raw` folder.
* Data Processor: Checks images for duplicates, validate image formats, converts images to TF Records
* Model Training: Submits training jobs to Vertex AI to train models
* Model Deploy: Updates trained models signature with preprocessing logic added to it. Upload model to Vertex AI Model Registry and Deploy model to Model Endpoints.
* API Service: FastAPI service to expose APIs to the frontend.
* Frontend:  React Frontend for the cheese app.
<img src="images/ci-cd.png"  width="800">

## Prerequisites
* Have Docker installed
* Cloned this repository to your local machine

## Setup Environments
In this tutorial we will setup a container to manage:
- Building docker images.
- Uploading Docker images ot GCR.
- Running ML jobs using Vertex AI pipelines.
- Deploying app containers to Kubernetes clusters

### Clone the github repository
- Clone repo from [here](https://github.com/dlops-io/cheese-app-v4)

### API's to enable in GCP for Project
Search for each of these in the GCP search bar and click enable to enable these API's
* Vertex AI API
* Compute Engine API
* Service Usage API
* Cloud Resource Manager API
* Google Container Registry API
* Kubernetes Engine API

### Setup GCP Service Account for deployment
- Here are the step to create a service account:
- To setup a service account you will need to go to [GCP Console](https://console.cloud.google.com/home/dashboard), search for  "Service accounts" from the top search box. or go to: "IAM & Admins" > "Service accounts" from the top-left menu and create a new service account called "deployment". 
- Give the following roles:
- For `deployment`:
    - Compute Admin
    - Compute OS Login
    - Container Registry Service Agent
    - Kubernetes Engine Admin
    - Service Account User
    - Storage Admin
    - Vertex AI Administrator
- Then click done.
- This will create a service account
- On the right "Actions" column click the vertical ... and select "Create key". A prompt for Create private key for "deployment" will appear select "JSON" and click create. This will download a Private key json file to your computer. Copy this json file into the **secrets** folder.
- Rename the json key file to `deployment.json`

Your folder structure should look like this:
```
   |-cheese-app-v4
      |-images
      |-src
        |---data-collector
        |---data-processor
        |---api-service
        |---frontend-react
        |---deployment
   |-secrets
```

### Replace GCP project id
The following files will need to be modified to replace the GCP project `ac215-project` to your GCP project id.

* inventory.yml
* inventory-prod.yml
* docker-shell.sh

## Ensure Kubernetes Cluster is Up

We deployed our cheese app to a Kubernetes cluster in the previous tutorial. In order to perform Continuous Integration and Continuous Deployment we will assume the cluster already exists. If your cluster is not running, follow these steps to create the cluster.

### Run `deployment` container
- cd into `deployment`
- Go into `docker-shell.sh` and change `GCP_PROJECT` to your project id
- Run `sh docker-shell.sh`


#### Build and Push Docker Containers to GCR (Google Container Registry)
Run this step only if you did not build + push images to GCR in our last tutorial.
```
ansible-playbook deploy-docker-images-app.yml -i inventory.yml
```

#### Create & Deploy Cluster
Run this step if you do not have a Kubernetes cluster running.
```
ansible-playbook deploy-k8s-cluster.yml -i inventory.yml --extra-vars cluster_state=present
```

#### View the App (If you have a domain)
* Copy the `nginx_ingress_ip` from the terminal from the create cluster command
* Go to your domain provider and in the DNS settings create a mapping from domain name to the `nginx_ingress_ip`
* Example: formaggio.me -> 34.148.61.120
* App url: http://formaggio.me


#### View the App (If you do not have a domain)
* Copy the `nginx_ingress_ip` from the terminal from the create cluster command
* Go to `http://<YOUR INGRESS IP>.sslip.io`

* Example: http://34.148.61.120.sslip.io/


## Setup GitHub Action Workflow Credentials

In this step we need to setup credentials in GitHub so that we can perform the following functions in GCP:
* Push docker images to GCR
* Run Vertex AI pipeline jobs
* Update kubernetes deployments 

### Setup
* Go to the repo Settings
* Select "Secrets and variable" from the left side menu and select "Actions"
* Under "Repository secrets" click "New repository secret"
* Give the Name as "GOOGLE_APPLICATION_CREDENTIALS"
* For the Secret copy+paste the contents of your secrets file `deployment.json` 

## Continuous Integration and Continuous Deployment (CI/CD) 

Continuous Integration and Continuous Delivery/Continuous Deployment (CI/CD) is a set of principles and practices in software development and operations aimed at frequently delivering code changes reliably and efficiently.

**Continuous Integration (CI):** Practice of regularly integrating code changes from multiple developers into a shared repository. The main goal is to detect integration issues early by automatically testing and building the code whenever a change is made. CI ensures that the codebase is always in a functional state.

**Continuous Delivery (CD):** This is an extension of CI, focusing on automating the delivery of applications to various environments, like staging or testing, in a way that they can be released to production at any time. The emphasis is on ensuring that the software can be deployed to a production environment and is ready for release but does not necessarily release it to the end users automatically.

**Continuous Deployment (CD):** This takes the automation a step further by automatically deploying code changes to production after they pass all the automated tests in the deployment pipeline. This approach allows for a rapid release cycle and is commonly used in scenarios where rapid deployment and iteration are essential.

### Frontend & Backend Changes

We have a GitHub Action that will build and deploy a new version of the app when a git commit has a comment `/run-deploy-app`

* Open the file `src` / `api-service` / `api` / `service.py`
* Update the version in line 29:
```
@app.get("/status")
async def get_api_status():
    return {
        "version": "3.1",
        "tf_version": tf.__version__,
    }
```
* Open the file `src` / `frontend-react` / `src` / `services` / `Common.js`
* Update the version in line 3:
```
export const APP_VERSION = 2.3;
```

To change the background color of the header in the frontend.
* Open the file `src` / `frontend-react` / `src` / `components` / `layout` / `Header.jsx`
* Update the background color in line 69 to `bg-sky-700`:
```
className={`fixed w-full top-0 z-50 transition-all duration-300 ${isScrolled ? 'bg-sky-700' : 'bg-transparent'
```

To run the deploy app action, add the following to code commit comment:
**Do this outside the container**

* Add `/deploy-app` to the commit message to re-deploy the frontend and backend 
### ML Component Changes

We can make changes to ML code and commit to GitHub and invoke running ML Tasks in Vertex AI

To run Vertex AI Pipelines on code commits, add the following to code commit comment:
* Add `/run-ml-pipeline` to the commit message to run the entire Vertex AI ML pipeline
* Add `/run-data-collector` to the commit message to run the data collector ML pipeline
* Add `/run-data-processor` to the commit message to run the data processor ML pipeline
