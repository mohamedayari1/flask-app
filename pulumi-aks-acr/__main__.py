"""An Azure RM Python Pulumi program"""

import pulumi
from pulumi_azure_native import containerservice, resources, containerregistry, authorization
from pulumi_azure_native.authorization import RoleAssignment
from pulumi_azure_native import operationalinsights
from pulumi import Output
import pulumi_azure_native as azure_native

# Step 1: Create a Resource Group
resource_group = resources.ResourceGroup("oratio-ai-law_chatbot-aks")

# Step 2: Create an Azure Container Registry (ACR)
acr = containerregistry.Registry(
    "myacrregistry",
    resource_group_name=resource_group.name,
    sku=containerregistry.SkuArgs(name="Basic"),
    admin_user_enabled=True
)

# Step 3: Create Log Analytics Workspace (required for AKS monitoring)
workspace = operationalinsights.Workspace(
    "aks-workspace",
    resource_group_name=resource_group.name,
    sku=operationalinsights.WorkspaceSkuArgs(
        name="PerGB2018"
    ),
    retention_in_days=30
)

# Step 4: Create the AKS cluster
aks = containerservice.ManagedCluster(
    "aksCluster",
    resource_group_name=resource_group.name,
    agent_pool_profiles=[containerservice.ManagedClusterAgentPoolProfileArgs(
        name="agentpool",
        mode="System",
        os_type="Linux",
        vm_size="Standard_DS2_v2",
        count=3
    )],
    dns_prefix="mypulumiaks",
    enable_rbac=True,
    addon_profiles={
        "omsagent": containerservice.ManagedClusterAddonProfileArgs(
            enabled=True,
            config={"logAnalyticsWorkspaceResourceID": workspace.id}
        )
    },
    identity=containerservice.ManagedClusterIdentityArgs(
        type="SystemAssigned"
    ),
    node_resource_group="aks_nodes_rg",
    service_principal_profile=containerservice.ManagedClusterServicePrincipalProfileArgs(
        client_id="msi"
    ),
)

# Step 5: Grant AKS access to ACR
role_assignment = RoleAssignment(
    "aksACRRoleAssignment",
    principal_id=aks.identity_profile["kubeletidentity"].object_id,
    role_definition_id="/subscriptions/15c9acc7-412b-40d2-94ec-6acc6f51d341/providers/Microsoft.Authorization/roleDefinitions/7f951dda-4ed3-4680-a7ca-43fe172d538d",
    scope=acr.id,
)


# Export the Kubernetes cluster's kubeconfig
kubeconfig = Output.secret(containerservice.list_managed_cluster_user_credentials_output(
    resource_group_name=resource_group.name,
    resource_name=aks.name,
)).kubeconfigs[0].value.apply(lambda enc: enc.decode("utf-8"))

pulumi.export("kubeconfig", kubeconfig)
pulumi.export("acr_login_server", acr.login_server)