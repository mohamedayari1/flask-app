import pulumi
from pulumi_azure_native import resources, containerservice, containerregistry
from pulumi_kubernetes import Provider, apps, core
from pulumi import Output

# Step 1: Create an Azure Resource Group
# --------------------------------------
# A resource group is a container that holds related resources for an Azure solution.
# Everything you deploy in Azure will live inside a resource group.
resource_group = resources.ResourceGroup("flask-rg")

# Step 2: Create an Azure Container Registry (ACR)
# ------------------------------------------------
# A Container Registry (ACR) is where you store Docker container images.
# We are creating a basic ACR with admin user access enabled.
acr = containerregistry.Registry(
    "flaskacr",
    resource_group_name=resource_group.name,  # The resource group we created earlier
    sku=containerregistry.SkuArgs(name="Basic"),  # The ACR pricing tier (Basic, Standard, Premium)
    admin_user_enabled=True  # Enables admin user to allow pulling images easily
)

# Step 3: Create an AKS cluster
# ------------------------------
# AKS (Azure Kubernetes Service) is a managed Kubernetes service.
# We define its configuration, such as node size, number of nodes, and Kubernetes version.
aks = containerservice.ManagedCluster(
    "aksdemocluster",
    resource_group_name=resource_group.name,  # Put the cluster in the same resource group
    agent_pool_profiles=[containerservice.ManagedClusterAgentPoolProfileArgs(
        name="nodepool1",  # The default node pool
        mode="System",  # The node pool mode (System means core system components run here)
        os_type="Linux",  # The operating system type for the nodes (Linux in this case)
        vm_size="Standard_DS2_v2",  # The size of the virtual machines for nodes (Standard_DS2_v2 is a common VM size)
        count=2,  # Number of nodes in the cluster
    )],
    dns_prefix="aksdemocluster",  # DNS prefix for accessing the AKS cluster API
    enable_rbac=True,  # Enables Role-Based Access Control (RBAC) for security
    kubernetes_version="1.24.0",  # The Kubernetes version to use
    identity=containerservice.ManagedClusterIdentityArgs(
        type="SystemAssigned"  # Managed identity for the cluster (Azure manages permissions automatically)
    )
)

# Step 4: Get credentials for the AKS cluster
# -------------------------------------------
# After creating the AKS cluster, you need to get its credentials (kubeconfig).
# The kubeconfig file is what gives Kubernetes clients access to the cluster.
credentials = containerservice.list_managed_cluster_user_credentials_output(
    resource_group_name=resource_group.name,  # Resource group where AKS lives
    resource_name=aks.name  # The AKS cluster name
)

# Convert kubeconfig (which is base64-encoded) into a string that Pulumi can use.
# This allows us to use the kubeconfig with Pulumi's Kubernetes provider.
kubeconfig = Output.secret(credentials.kubeconfigs[0].value).apply(
    lambda enc: enc.decode("utf-8")  # Convert base64 to utf-8 string
)

# Step 5: Create a Kubernetes provider that uses the AKS cluster
# --------------------------------------------------------------
# Pulumi's Kubernetes provider allows us to deploy Kubernetes resources like Pods, Services, etc.
# Here, we pass the kubeconfig from the AKS cluster, so Pulumi can manage the AKS Kubernetes cluster.
k8s_provider = Provider("k8s-provider", kubeconfig=kubeconfig)

# Step 6: Deploy the Flask Application to AKS
# -------------------------------------------
# We are now creating a Kubernetes Deployment for the Flask app.
# A Deployment ensures that a specific number of replicas (pods) of your application are running.
deployment = apps.v1.Deployment(
    "flask-app-deployment",  # The name of the Kubernetes deployment
    metadata={"name": "flask-app", "labels": {"app": "flask"}},  # Labels help organize resources in Kubernetes
    spec=apps.v1.DeploymentSpecArgs(
        replicas=2,  # The number of Pods to run for this app (2 replicas)
        selector=core.v1.LabelSelectorArgs(
            match_labels={"app": "flask"}  # This matches the Pods by label
        ),
        template=core.v1.PodTemplateSpecArgs(  # The Pod template defines how each Pod should be created
            metadata={"labels": {"app": "flask"}},  # Labels to apply to each Pod
            spec=core.v1.PodSpecArgs(
                containers=[core.v1.ContainerArgs(  # Define the container inside each Pod
                    name="flask-app",  # Container name
                    image=f"{acr.login_server}/k8sflask:latest",  # The container image from ACR
                    ports=[core.v1.ContainerPortArgs(container_port=8080)]  # The Flask app listens on port 8080
                )]
            )
        )
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider)  # Use the AKS provider to manage this Deployment
)

# Step 7: Expose the Flask Application using a LoadBalancer Service
# -----------------------------------------------------------------
# A Kubernetes Service exposes your app to the network (LoadBalancer makes it publicly accessible).
# The service forwards traffic from port 80 (the default HTTP port) to the Flask app's port 8080.
service = core.v1.Service(
    "flask-service",  # The service name
    metadata={"name": "flask-svc"},  # Metadata for the service
    spec=core.v1.ServiceSpecArgs(
        selector={"app": "flask"},  # This service routes traffic to Pods labeled "app: flask"
        ports=[core.v1.ServicePortArgs(port=80, target_port=8080)],  # Expose port 80 and forward to port 8080 in the Pod
        type="LoadBalancer",  # Use LoadBalancer to make the app accessible on a public IP
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider)  # Use the AKS provider to manage this Service
)

# Step 8: Grant AKS Cluster access to ACR
# ---------------------------------------
# To let the AKS cluster pull images from ACR, we create a Kubernetes Secret
# that contains the credentials for the ACR (Azure Container Registry).
acr_credentials = containerregistry.ListRegistryCredentialsOutput(
    resource_group_name=resource_group.name,  # The resource group that holds the ACR
    registry_name=acr.name  # The ACR name
)

# Create a Kubernetes secret to hold the ACR credentials, allowing the cluster to pull images from ACR.
pull_secret = core.v1.Secret(
    "acr-pull-secret",
    metadata={"name": "k8s-secret"},  # Name the secret 'k8s-secret'
    type="kubernetes.io/docker-registry",  # This is a Docker registry secret type
    data={
        ".dockerconfigjson": acr_credentials.apply(lambda creds: creds.passwords[0].value)  # Store the ACR credentials
    },
    opts=pulumi.ResourceOptions(provider=k8s_provider)  # Apply this secret in the AKS cluster
)

# Step 9: Output the external IP address of the Flask application
# ---------------------------------------------------------------
# The LoadBalancer service will assign a public IP to your app. We output this IP address so you can use it to access the app.
pulumi.export("flask-app-ip", service.status.apply(lambda status: status.load_balancer.ingress[0].ip))
