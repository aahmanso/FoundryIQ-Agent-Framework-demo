metadata description = 'Creates an Azure AI Services (Foundry) resource with project management, model deployment, and child project.'

param name string
param location string = resourceGroup().location
param tags object = {}

@description('Model deployment name')
param modelName string = 'gpt-4.1'

@description('Model version')
param modelVersion string = '2025-04-14'

@description('Model deployment capacity (TPM in thousands)')
param modelCapacity int = 30

@description('Model deployment SKU')
param modelSkuName string = 'GlobalStandard'

@description('Child project name')
param projectName string

// AIServices account with project management enabled
// Uses 2025-04-01-preview which supports allowProjectManagement
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    #disable-next-line BCP037
    allowProjectManagement: true
  }
}

// Deploy model to AIServices
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: modelName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// Foundry Project under AIServices
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
  dependsOn: [modelDeployment]
}

output id string = aiServices.id
output name string = aiServices.name
output endpoint string = aiServices.properties.endpoint
output principalId string = aiServices.identity.principalId
output projectPrincipalId string = project.identity.principalId
output projectEndpoint string = 'https://${name}.services.ai.azure.com/api/projects/${projectName}'
