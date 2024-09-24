<!-- #Initialize pulumi -->
pulumi stack init dev
pulumi config set azure:location <your-region>  # Set the region, e.g., eastus

<!-- Run Pulumi -->
pulumi up
