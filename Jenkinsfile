pipeline {
  agent {
    kubernetes {
      yaml """
  apiVersion: v1
  kind: Pod
  spec:
    serviceAccountName: jenkins
    restartPolicy: Never
    nodeSelector:
      kubernetes.io/os: linux
    containers:
      - name: kaniko
        image: gcr.io/kaniko-project/executor:v1.23.2-debug
        command: ["/busybox/cat"]
        tty: true
        env:
          - name: AWS_REGION
            value: "us-east-1"
          - name: AWS_SDK_LOAD_CONFIG
            value: "true"
        resources:
          requests:
            memory: "1200Mi"
            cpu: "500m"
          limits:
            memory: "3Gi"
            cpu: "2000m"
        volumeMounts:
          - name: docker-config
            mountPath: /kaniko/.docker
          - name: workspace-volume
            mountPath: /home/jenkins/agent

      - name: tools
        image: alpine:3.19
        command: ["/bin/sh", "-c", "cat"]
        tty: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
          - name: docker-config
            mountPath: /docker-config
          - name: workspace-volume
            mountPath: /home/jenkins/agent

    volumes:
      - name: docker-config
        emptyDir: {}
      - name: workspace-volume
        emptyDir: {}
  """
    }
  }

  options {
    disableConcurrentBuilds()
  }

  environment {
    AWS_REGION          = "us-east-1"
    AWS_ACCOUNT_ID      = "614520203750"
    ECR_REGISTRY        = "614520203750.dkr.ecr.us-east-1.amazonaws.com"
    IMAGE_REPO          = "614520203750.dkr.ecr.us-east-1.amazonaws.com/tfm-mlops-inference"

    NAMESPACE           = "apps"
    RELEASE             = "inference"
    DEPLOYMENT          = "inference-inference"
    CHART_PATH          = "tfm-mlops-eks/helm/inference-service"

    SERVICE_DIR         = "tfm-mlops-eks/service"
    PAYLOAD_FILE        = "payload.json"

    MLFLOW_TRACKING_URI = "http://mlflow.mlops.svc.cluster.local:5000"
    MODEL_URI           = "runs:/b2c10be3e0914140be1756a597a2e678/model"
    THRESHOLD           = "0.5"

    REPLICA_COUNT       = "2"
    CPU_REQUEST         = "500m"
    CPU_LIMIT           = "1"
    MEMORY_REQUEST      = "512Mi"
    MEMORY_LIMIT        = "1Gi"

    GITLEAKS_VERSION    = "8.18.1"
  }

  stages {
    stage("Checkout") {
      steps {
        checkout scm
      }
    }

    stage("Verify repo paths") {
      steps {
        container("tools") {
          sh '''
            set -e
            test -f "${SERVICE_DIR}/Dockerfile"
            test -f "${CHART_PATH}/Chart.yaml"
            test -f "${PAYLOAD_FILE}"
            echo "Repo structure OK"
          '''
        }
      }
    }

    stage("Security - Gitleaks") {
      steps {
        container("tools") {
          sh '''
            set +e
            apk add --no-cache curl tar file

            curl -L -o /tmp/gitleaks.tar.gz "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
            file /tmp/gitleaks.tar.gz
            tar -xzf /tmp/gitleaks.tar.gz -C /tmp

            /tmp/gitleaks version || true
            /tmp/gitleaks detect --source . --no-git --redact || true
            exit 0
          '''
        }
      }
    }

    stage("Build & Push (Kaniko -> ECR)") {
      steps {
        withCredentials([
          usernamePassword(
            credentialsId: 'aws-creds',
            usernameVariable: 'AWS_ACCESS_KEY_ID',
            passwordVariable: 'AWS_SECRET_ACCESS_KEY'
          )
        ]) {
          container("tools") {
            sh '''
              set -euo pipefail
              apk add --no-cache aws-cli coreutils
              aws --version

              PASS=$(aws ecr get-login-password --region "${AWS_REGION}")
              AUTH=$(printf "AWS:%s" "$PASS" | base64 | tr -d '\\n')

              cat > /docker-config/config.json <<EOF
{
  "auths": {
    "${ECR_REGISTRY}": {
      "auth": "${AUTH}"
    }
  }
}
EOF

              echo "Docker config created for ${ECR_REGISTRY}"
            '''
          }

          container("kaniko") {
            sh '''
              set -euo pipefail
              /kaniko/executor \
                --context "${WORKSPACE}/${SERVICE_DIR}" \
                --dockerfile "${WORKSPACE}/${SERVICE_DIR}/Dockerfile" \
                --destination "${IMAGE_REPO}:${BUILD_NUMBER}" \
                --destination "${IMAGE_REPO}:latest" \
                --snapshotMode=redo
            '''
          }
        }
      }
    }

    stage("Security - Trivy") {
      steps {
        withCredentials([
          usernamePassword(
            credentialsId: 'aws-creds',
            usernameVariable: 'AWS_ACCESS_KEY_ID',
            passwordVariable: 'AWS_SECRET_ACCESS_KEY'
          )
        ]) {
          container("tools") {
            sh '''
              set +e
              apk add --no-cache aws-cli curl
              aws --version

              curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
              trivy --version || true

              PASS=$(aws ecr get-login-password --region "${AWS_REGION}")
              trivy image \
                --username AWS \
                --password "$PASS" \
                --severity HIGH,CRITICAL \
                --no-progress \
                "${IMAGE_REPO}:${BUILD_NUMBER}" || true

              exit 0
            '''
          }
        }
      }
    }

    stage("Install kubectl & Helm") {
      steps {
        container("tools") {
          sh '''
            set -euo pipefail
            apk add --no-cache curl bash git tar

            curl -sSL https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz | tar -xz
            mv linux-amd64/helm /usr/local/bin/helm
            chmod +x /usr/local/bin/helm
            helm version

            curl -LO https://dl.k8s.io/release/v1.29.15/bin/linux/amd64/kubectl
            install -m 0755 kubectl /usr/local/bin/kubectl
            kubectl version --client
          '''
        }
      }
    }

    stage("Deploy (Helm)") {
      steps {
        container("tools") {
          sh '''
            set -euo pipefail

            kubectl get ns "${NAMESPACE}" >/dev/null 2>&1 || kubectl create ns "${NAMESPACE}"

            helm lint "${CHART_PATH}"

            helm upgrade --install "${RELEASE}" "${CHART_PATH}" -n "${NAMESPACE}" \
              --set-string image.repository="${IMAGE_REPO}" \
              --set-string image.tag="${BUILD_NUMBER}" \
              --set replicaCount="${REPLICA_COUNT}" \
              --set-string env.MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI}" \
              --set-string env.MODEL_URI="${MODEL_URI}" \
              --set-string env.THRESHOLD="${THRESHOLD}" \
              --set-string resources.requests.cpu="${CPU_REQUEST}" \
              --set-string resources.limits.cpu="${CPU_LIMIT}" \
              --set-string resources.requests.memory="${MEMORY_REQUEST}" \
              --set-string resources.limits.memory="${MEMORY_LIMIT}" \
              --atomic --wait --timeout 10m

            kubectl -n "${NAMESPACE}" rollout status deploy/"${DEPLOYMENT}" --timeout=10m
            kubectl -n "${NAMESPACE}" get pods -o wide
          '''
        }
      }
    }

    stage("Smoke test") {
      steps {
        container("tools") {
          sh '''
            set -euo pipefail
            apk add --no-cache curl

            SVC=$(kubectl -n "${NAMESPACE}" get svc -l app.kubernetes.io/instance="${RELEASE}" -o jsonpath='{.items[0].metadata.name}')
            kubectl -n "${NAMESPACE}" port-forward svc/$SVC 18080:80 >/tmp/pf.log 2>&1 &
            PF_PID=$!
            trap "kill $PF_PID" EXIT

            sleep 5

            curl -sf http://127.0.0.1:18080/health
            curl -sf -X POST http://127.0.0.1:18080/predict \
              -H "Content-Type: application/json" \
              --data @"${PAYLOAD_FILE}"
          '''
        }
      }
    }
  }

  post {
    always {
      container("tools") {
        sh '''
          echo "Pipeline finished. Build=${BUILD_NUMBER}"
        '''
      }
    }
  }
}