# Kubernetes Deployment (F13)

## Overview
Kubernetes configuration for production deployment with autoscaling.

## Components

### Deployments
- `bot-deployment.yaml` - Main Telegram bot
- `bridge-deployment.yaml` - Bridge bot
- `vk-bot-deployment.yaml` - VK bot
- `metrics-deployment.yaml` - Prometheus metrics

### Services
- Load balancing for bot services
- Internal networking

### HPA (Horizontal Pod Autoscaler)
- Scale based on CPU/memory usage
- Min 1, Max 5 replicas

### ConfigMaps & Secrets
- Environment variables
- Bot tokens

## Files

```
k8s/
├── bot-deployment.yaml
├── bridge-deployment.yaml
├── vk-bot-deployment.yaml
├── metrics-deployment.yaml
├── service.yaml
├── ingress.yaml
├── hpa.yaml
├── configmap.yaml
└── secrets.yaml
```

## Deployment Steps

1. Build Docker images
2. Push to registry
3. Apply k8s configs:
   ```bash
   kubectl apply -f k8s/
   ```

## Monitoring
- Prometheus Operator
- Grafana dashboards
- AlertManager for alerts

## Scaling Policy
```yaml
resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```
