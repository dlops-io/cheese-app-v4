rm .docker-tag
ansible-playbook deploy-docker-images-app.yml -i inventory.yml
ansible-playbook update-k8s-cluster.yml -i inventory-prod.yml