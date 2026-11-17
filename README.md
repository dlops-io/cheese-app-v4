# Cheese App - Automation

In `cheese-app-v3` we deployed the Cheese App to GKE from our laptop, one command at a time. In this
tutorial GitHub does it for us, every time we push:

| Tutorial | What it shows |
| --- | --- |
| [Checks before you commit](#tutorial-checks-before-you-commit) | A git hook lints and formats the files you commit, and stops a commit with a key in it |
| [Continuous integration](#tutorial-continuous-integration) | Every push is tested, linted and built, and a broken one is marked in red |
| [Deploy the app with a commit](#tutorial-deploy-the-app-with-a-commit) | `/deploy-app` in a commit message ships the change to the cluster, a pod at a time |
| [Train the model with a commit](#tutorial-train-the-model-with-a-commit) | `/run-ml-pipeline` collects photos, trains a new model on Vertex AI and puts it in the app |

![CI/CD for the Cheese App: a git push runs CI on GitHub Actions. With /deploy-app, the Deploy app workflow pushes images to Artifact Registry and rolls them out to GKE. With /run-ml-pipeline, the ML pipeline workflow runs Vertex AI Pipelines, which write the model to the ML bucket, and the API loads it](images/ci-cd.svg)

The app is `cheese-app-v3`'s, plus three containers that make the model the app's **Identify** mode
uses:

| Folder | What it is | Where it runs |
| --- | --- | --- |
| `src/api-service/` | FastAPI: content, and chat with Gemini, the CNN and RAG | GKE |
| `src/frontend-react/` | The page, served by nginx, which passes `/api` to the API | GKE |
| `src/vector-db/` | Chroma, and the Job that loads the cheese books into it | GKE |
| `src/data-collector/` | Searches the web for photos of each cheese | Vertex AI Pipelines |
| `src/data-processor/` | Drops broken photos and near-duplicates, and makes the rest JPEGs | Vertex AI Pipelines |
| `src/model-training/` | Fine-tunes MobileNetV2 on the photos and saves the model | Vertex AI Pipelines |
| `src/deployment/` | The deployment container: Pulumi, the Kubernetes YAML and the scripts | Your laptop, and GitHub Actions |
| `src/checks/` | The checks container: the linters and formatters the git hook and CI run | Your laptop, and GitHub Actions |
| `.github/workflows/` | The three workflows GitHub runs | GitHub Actions |

## Prerequisites
- The `cheese-app-v3` tutorials on Google Cloud, done: the Google Cloud setup, its service accounts
  and the `deployment.json` key
- A GitHub account, and the GitHub repository from the next section
- A project with billing on. The cluster costs money every hour it runs, and each pipeline run costs a
  little, so delete the cluster when you are done.

## Tutorial: Setup
Do this once.

### Your own copy of the repository
GitHub runs the workflows in your repository, with your key, so you need your own copy:
1. On [cheese-app-v4](https://github.com/dlops-io/cheese-app-v4), choose **Fork**.
2. In your fork, open **Actions** and choose **I understand my workflows, go ahead and enable them**.
   GitHub turns workflows off in a new fork.
3. Clone your fork, next to the **secrets** folder from `cheese-app-v3`:
```
   |-cheese-app-v4
     |-.github
       |---workflows
     |-docs
     |-images
     |-src
       |---api-service
       |---checks
       |---data-collector
       |---data-processor
       |---deployment
       |---frontend-react
       |---model-training
       |---vector-db
   |-secrets
     |---deployment.json
     |---ml-workflow.json     (for api-service and vector-db's own docker-shell.sh)
```

### Service accounts
These are `cheese-app-v3`'s two accounts, with one more role for `deployment`: it now also starts the
ML pipeline on Vertex AI. In the console, go to **IAM & Admin > IAM**, edit each account and check its
roles:

| Account | Roles | Used by |
| --- | --- | --- |
| `deployment` | Compute Admin, Artifact Registry Administrator, Kubernetes Engine Admin, Storage Admin, Service Account User, Service Account Admin, **Agent Platform User** | The deployment container, on your laptop and on GitHub |
| `gcp-service` | Agent Platform User, Artifact Registry Reader | The API on GKE, and the pipeline's steps on Vertex AI |

Agent Platform User is `roles/aiplatform.user`, called Vertex AI User before. Not **AI Platform Admin**:
that is an older product's role, and with it Vertex AI answers 403.

### Set your project
Replace `ac215-project` with your project ID:
- At the top of `src/deployment/docker-shell.sh`
- In `src/deployment/deploy_base/Pulumi.dev.yaml` (twice), `src/deployment/deploy_images/Pulumi.dev.yaml`
  and `src/deployment/deploy_k8s/Pulumi.dev.yaml` (three times)

Commit and push this change, so GitHub uses your project too.

### The cluster and the ML bucket
The workflows deploy to the cluster from `cheese-app-v3`: the stacks have the same names, so they find
it. In the deployment container:
```bash
cd src/deployment
```

```bash
./docker-shell.sh
```

1. `deploy_base` now also makes the ML bucket, `<your project>-cheese-app-ml`, where the pipeline keeps
   its photos and models. Run it again even if you ran it in `cheese-app-v3`:
```bash
cd /app/deploy_base && pulumi stack select dev --create && pulumi up --stack dev -y
```

2. If your cluster is gone, create it again. About 11 minutes:
```bash
cd /app/deploy_k8s && pulumi stack select dev --create && pulumi up --stack dev -y
```

3. Deploy the app once from here, the same way GitHub will. It builds and pushes the images, six now,
   then rolls them out. The first time takes several minutes; the load balancer takes about 2 more
   before the address answers:
```bash
cd /app && ./scripts/deploy-app.sh
```

### Tell GitHub your project and key
In your fork, open **Settings > Secrets and variables > Actions**:
1. Under **Secrets**, choose **New repository secret**. Name: `GOOGLE_APPLICATION_CREDENTIALS`. Secret:
   paste everything in your `deployment.json`.
2. Under **Variables**, choose **New repository variable**. Name: `GCP_PROJECT`. Value: your project ID.
   `GCP_REGION` and `GCP_ZONE` are optional: `us-central1` and `us-central1-a` unless you set them.

GitHub never shows a secret again, not even to you, and hides it in the workflows' logs. It is still
your deployment key: anyone who can change the workflows in your repository can use it, so keep the
repository's write access to yourself.

## Tutorial: Checks before you commit
Before each commit, a git hook checks the files you are committing. The checks run in Docker, in the
checks container (`src/checks/`), so you need only git and Docker: no Python, Node or linters on your
laptop. They are listed in `.pre-commit-config.yaml`, and run by [pre-commit](https://pre-commit.com):

| Check | Tool | Fixes it for you |
| --- | --- | --- |
| Spaces at line ends, a newline at the end of each file | pre-commit-hooks | Yes |
| YAML, JSON and TOML parse, no merge conflict markers, no new file over 1 MB | pre-commit-hooks | No |
| No private keys, passwords or API keys | `detect-private-key`, `gitleaks` | No |
| Python lint and format, with each folder's `pyproject.toml` | `ruff` | Mostly |
| Shell scripts | `shellcheck` | No |
| GitHub Actions workflows | `actionlint` | No |
| Frontend format and lint, with the frontend's own versions and settings | `prettier`, `eslint` | prettier does |

1. Turn the hook on. Git does not copy hooks with a clone, so do this once in each clone, from its top
   folder:
```bash
git config core.hooksPath .githooks
```

2. Commit some badly formatted Python: an import it never uses, and odd spacing:
```bash
printf 'import os\ndef shout( word ):\n    return word.upper( )+"!"\n' > src/data-processor/try_hook.py
```

```bash
git add src/data-processor/try_hook.py && git commit -m "Try the hook"
```

   The first time, Docker builds the checks container, about a minute; after that a commit waits a few
   seconds. **Python lint (ruff)** and **Python format (ruff)** fail, and no commit is made. They have
   fixed the file already: `git diff` shows the import gone and the spacing tidied.

3. Add the fixed file and commit again. Every check passes:
```bash
git add src/data-processor/try_hook.py && git commit -m "Try the hook"
```

4. Delete the file again:
```bash
git rm -q src/data-processor/try_hook.py && git commit -m "Remove the hook example"
```

A file with a private key in it, like `deployment.json`, stops the commit the same way: **No private
keys** and **No keys or passwords (gitleaks)** fail, and nothing has left your laptop yet.

To run the checks without committing:
```bash
src/checks/run.sh
```

```bash
src/checks/run.sh --all-files
```

The first checks the files you have staged; the second checks every file, as CI does.
`git commit --no-verify` skips the hook, but not CI: the **Lint and format checks** job in the next
tutorial runs the same checks on every file.

## Tutorial: Continuous integration
`ci.yml` runs on every push, to any branch. It needs no key and touches nothing on Google Cloud. Like
the hook, every job runs in Docker, in the same containers you use on your laptop:

| Job | What it checks | In which container |
| --- | --- | --- |
| Lint and format checks | The git hook's checks, on every file | The checks container |
| API tests | `pytest` | The API's development image (`Dockerfile.dev`) |
| Deployment checks | `./scripts/check.sh`: `ruff` and `shellcheck`, the Kubernetes YAML renders, the ML pipeline compiles | The deployment container |
| Build (one per image) | Each of the six production images builds; the frontend's runs `vite build` | Each image's own `Dockerfile` |

1. Make a branch, change anything and push it:
```bash
git switch -c try-ci
```

```bash
git commit --allow-empty -m "Try CI"
```

```bash
git push -u origin try-ci
```

2. Open **Actions** in your fork, then the **CI** run. The jobs run side by side.

3. Now break a test. In `src/api-service/api/service.py`, change `"version": "4.0.0"` to `"4.1.0"`, then
   commit and push. **API tests** turns red: `tests/test_service.py` still expects `4.0.0`. Put it back
   (or fix the test), push again, and it is green.

On a pull request, GitHub shows the same checks next to the merge button. That is what CI is for:
nothing reaches `main`, and from there the cluster, without them.

## Tutorial: Deploy the app with a commit
`deploy-app.yml` runs on pushes to `main` whose commit message contains `/deploy-app`. It runs CI first,
and only if CI passes, runs `./scripts/deploy-app.sh` in the deployment container, the command you ran
in the setup:
- `pulumi up` on `deploy_images` builds and pushes only the images whose files changed: each tag is a
  hash of its folder
- `deploy-k8s.sh` points the workloads at the new images. Kubernetes replaces those pods one at a time,
  and the others never restart.

1. Make a change you can see:
   - `src/frontend-react/src/lib/api.js`: `APP_VERSION = '4.1.0'`
   - `src/api-service/api/service.py`: `"version": "4.1.0"`, and `4.1.0` in `tests/test_service.py`
   - `src/frontend-react/src/App.jsx`: add `bg-sky-700` to the `<header>`'s `className`

2. Commit with `/deploy-app` in the message, on `main`, and push:
```bash
git switch main
```

```bash
git commit -am "Version 4.1.0 and a blue header /deploy-app"
```

```bash
git push
```

3. Open **Actions**, then the **Deploy app** run: first **CI**, then **Deploy to GKE**.

4. In the deployment container, watch the pods change:
```bash
kubectl -n cheese-app get pods -w
```

5. Reload the app. The header is blue, and the footer says `Frontend 4.1.0 · API 4.1.0`.

To deploy without a commit, open **Actions > Deploy app > Run workflow**.

Things to know:
- GitHub looks at the newest commit of a push only: put `/deploy-app` in that one.
- One Google Cloud change runs at a time. A second deploy, or an ML run, waits for the first.
- The workflow and your laptop run the same script in the same container. When a deploy fails on
  GitHub, run `./scripts/deploy-app.sh` in your deployment container and you will see the same thing.

## Tutorial: Train the model with a commit
**Identify** names the cheese in a photo with a CNN. Until now it came from GitHub, trained for you.
Here we train our own, on photos we collect, in three steps on Vertex AI Pipelines. The steps pass
their work to each other through the ML bucket:

| Step | Folder | Reads | Writes to the ML bucket |
| --- | --- | --- | --- |
| Collect | `data-collector` | Bing image search | `raw.zip`: 50 photos for each of brie, gouda, gruyere and parmigiano |
| Process | `data-processor` | `raw.zip` | `clean.zip`: no broken photos or near-duplicates, all JPEGs |
| Train | `model-training` | `clean.zip` | `models/<run>/model.keras`, `data_details.json`, `metrics.json`, then `models/latest` |

The API reads `models/latest` when it starts. Before the first training, it uses the model from GitHub.

1. Commit with `/run-ml-pipeline` in the message, on `main`, and push. The commit needs no changes:
```bash
git commit --allow-empty -m "Train a new model /run-ml-pipeline"
```

```bash
git push
```

2. Open **Actions**, then the **ML pipeline** run. After CI, it builds the ML images that changed and
   starts the pipeline. Follow the steps in the console: **Vertex AI > Pipelines**.

3. When training is done, the workflow restarts the API's pods, one at a time, so they load the new
   model. The footer shows it: `Model <run>`, the time it was trained. Try **Identify** with a photo.

4. See what the steps wrote:
```bash
gcloud storage ls gs://$GCP_PROJECT-cheese-app-ml/ gs://$GCP_PROJECT-cheese-app-ml/models/
```

```bash
gcloud storage cat gs://$GCP_PROJECT-cheese-app-ml/models/latest
```

One step at a time:

| In the commit message | Runs |
| --- | --- |
| `/run-ml-pipeline` | Collect, process, train |
| `/run-data-collector` | Collect |
| `/run-data-processor` | Process |
| `/run-model-training` | Train, on the photos already in the bucket |

Or open **Actions > ML pipeline > Run workflow** and choose the steps. From the deployment container,
the same script runs it, and `PER_LABEL` and `EPOCHS` change how many photos and how long it trains:
```bash
PER_LABEL=50 EPOCHS=10 ./scripts/run-ml-pipeline.sh
```

### Work on a step on your laptop
Each ML folder has a `docker-shell.sh`, like `cheese-app-v2`'s, that runs its container against your ML
bucket, with `deployment.json`, which can read and write it. Change `GCP_PROJECT` at its top first. For
example:
```bash
cd src/model-training
```

```bash
./docker-shell.sh cli.py --bucket ac215-project-cheese-app-ml --epochs 3
```

## Review the code
| File | What it does |
| --- | --- |
| `.pre-commit-config.yaml` | The checks before each commit, and in CI |
| `.githooks/pre-commit` | The git hook: runs `src/checks/run.sh` |
| `src/checks/run.sh` | Builds the checks container, then runs pre-commit in it on your repo |
| `src/checks/Dockerfile` | Each linter copied from its own official image, at a pinned version |
| `.github/workflows/ci.yml` | The checks on every push. The other two workflows run it first |
| `.github/workflows/deploy-app.yml` | `/deploy-app`: writes the key, then `./docker-shell.sh ./scripts/deploy-app.sh` |
| `.github/workflows/ml-pipeline.yml` | `/run-…`: reads the steps from the commit message, then `./docker-shell.sh ./scripts/run-ml-pipeline.sh` |
| `src/deployment/docker-shell.sh` | The deployment container. With a script after it, it runs that script and stops |
| `src/deployment/scripts/deploy-app.sh` | `pulumi up` on `deploy_images`, then `deploy-k8s.sh` |
| `src/deployment/scripts/run-ml-pipeline.sh` | Builds the images, runs the steps, restarts the API |
| `src/deployment/ml/pipeline.py` | The pipeline: one container step per folder, run as `gcp-service` |
| `src/deployment/deploy_base/__main__.py` | The static IP, the registry, the chat bucket and the ML bucket |
| `src/deployment/deploy_images/__main__.py` | The six images, each tagged with a hash of its folder |
| `src/data-collector/downloader.py` | Reads Bing's image search, the way a browser does |
| `src/data-processor/cli.py` | Finds near-duplicates with an 8x8 fingerprint of each photo |
| `src/model-training/cli.py` | MobileNetV2 trained on ImageNet, frozen, with a new last layer for our cheeses |
| `src/api-service/api/utils/llm_cnn_utils.py` | Loads `models/latest` from the ML bucket, or the model from GitHub |

Three things to notice in the workflows:
- A commit message is text anyone with push access can type. The ML workflow reads it from a variable
  and never pastes it into a command, where a message like `$(…)` would run.
- `concurrency: gcp-deploy` sits on the deploy jobs, not on the workflows: every push to `main` starts
  both workflows, and only the ones with a command should wait in line.
- Nothing in a workflow builds or deploys by itself: they call the scripts you can run, so the
  laptop and GitHub never drift apart.

## Kubernetes on your laptop
The kind cluster from `cheese-app-v3` works here too, in the deployment container. It uses the model
from GitHub, since it has no ML bucket:
```bash
./scripts/create-cluster-kind.sh
```

```bash
./scripts/deploy-kind.sh
```

Then open http://localhost:8090. `./scripts/delete-cluster-kind.sh` deletes it.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `The checks run in Docker, and Docker is not running` | Start Docker, then commit again |
| A check says `files were modified by this hook` | It fixed them: look with `git diff`, `git add` them, commit again |
| **Lint and format checks** is red, but your commits passed | The hook is off in that clone: `git config core.hooksPath .githooks`, then `src/checks/run.sh --all-files` |
| No workflows run in your fork | Open **Actions** and enable them |
| `Set the repository variable GCP_PROJECT` | Add the variable, as in the setup |
| `Add the repository secret GOOGLE_APPLICATION_CREDENTIALS` | Add the secret, as in the setup |
| A push to `main` does not deploy | Put `/deploy-app` in the newest commit's message, or use **Run workflow** |
| Deploy fails on `cluster_name` | No cluster: create it with `deploy_k8s`, as in the setup |
| ML pipeline fails with `aiplatform.pipelineJobs.create` | Give `deployment` the Agent Platform User role |
| ML pipeline fails with `iam.serviceAccounts.actAs` | Give `deployment` the Service Account User role |
| `No photos found for …: has Bing changed its page?` | Bing changed its search page. `src/data-collector/downloader.py` is the file to fix |
| `Only … photos of …: collect more first` | Run it again with more photos: `PER_LABEL=80` |
| Ask says `Gemini: 403 ... aiplatform.endpoints.predict` | `gcp-service` lacks **Agent Platform User** (`roles/aiplatform.user`) |
| The footer says `Model experiment_…` after training | The API had not restarted: `kubectl -n cheese-app rollout restart deployment/api-service` |

## Cleanup
Delete the cluster, from the deployment container. About 15 minutes:
```bash
cd /app && ./scripts/destroy-k8s.sh
```

A pipeline leaves nothing running. To delete the photos and models too, along with the static IP, the
registry and the chats:
```bash
cd /app/deploy_base && pulumi destroy --stack dev -y
```
