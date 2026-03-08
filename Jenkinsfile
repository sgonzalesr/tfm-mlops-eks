pipeline {
  agent {
    kubernetes {
      yaml """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins
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
    volumeMounts:
    - name: docker-config
      mountPath: /kaniko/.docker
    - name: aws-config
      mountPath: /root/.aws
  - name: tools
    image: alpine:3.19
    command: ["/bin/sh","-c","cat"]
    tty: true
    volumeMounts:
    - name: docker-config
      mountPath: /docker-config
    - name: aws-config
      mountPath: /root/.aws
  volumes:
  - name: docker-config
    emptyDir: {}
  - name: aws-config
    emptyDir: {}
"""
    }
  }

  environment {
    AWS_REGION   = "us-east-1"
    NAMESPACE    = "apps"
    RELEASE      = "inference"
    CHART_PATH   = "helm/inference-service"
    ECR_REGISTRY = "614520203750.dkr.ecr.us-east-1.amazonaws.com"
    IMAGE_REPO   = "614520203750.dkr.ecr.us-east-1.amazonaws.com/tfm-mlops-inference"
  }

  stages {
    stage("Checkout") {
      steps {
        checkout scm
      }
    }

    stage("Security - Gitleaks") {
      steps {
        container("tools") {
          sh '''
            apk add --no-cache curl git tar
            curl -sSL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_x64.tar.gz | tar -xz
            ./gitleaks detect --source . --no-git --redact
          '''
        }
      }
    }

    stage("Build & Push (Kaniko -> ECR)") {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          container("tools") {
            sh '''
              apk add --no-cache python3 py3-pip coreutils
              pip3 install --no-cache-dir awscli

              mkdir -p /root/.aws /docker-config

              cat > /root/.aws/credentials <<EOF
[default]
aws_access_key_id=${AWS_ACCESS_KEY_ID}
aws_secret_access_key=${AWS_SECRET_ACCESS_KEY}
region=${AWS_REGION}
EOF

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
            '''
          }

          container("kaniko") {
            sh '''
              /kaniko/executor \
                --context "${WORKSPACE}/service" \
                --dockerfile "${WORKSPACE}/service/Dockerfile" \
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
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          container("tools") {
            sh '''
              apk add --no-cache python3 py3-pip curl
              pip3 install --no-cache-dir awscli
              curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

              PASS=$(aws ecr get-login-password --region "${AWS_REGION}")
              trivy image --username AWS --password "$PASS" --severity HIGH,CRITICAL --no-progress "${IMAGE_REPO}:${BUILD_NUMBER}"
            '''
          }
        }
      }
    }

    stage("Deploy (Helm)") {
      steps {
        container("tools") {
          sh '''
            apk add --no-cache curl bash git tar
            curl -sSL https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz | tar -xz
            mv linux-amd64/helm /usr/local/bin/helm

            curl -LO https://dl.k8s.io/release/v1.29.15/bin/linux/amd64/kubectl
            install -m 0755 kubectl /usr/local/bin/kubectl

            helm upgrade --install "${RELEASE}" "${CHART_PATH}" -n "${NAMESPACE}" \
              --set image.repository="${IMAGE_REPO}" \
              --set-string image.tag="${BUILD_NUMBER}" \
              --atomic --wait --timeout 10m

            kubectl -n "${NAMESPACE}" rollout status deploy/${RELEASE}-inference --timeout=10m
          '''
        }
      }
    }

    stage("Smoke test") {
      steps {
        container("tools") {
          sh '''
            apk add --no-cache curl
            SVC=$(kubectl -n "${NAMESPACE}" get svc -l app.kubernetes.io/instance="${RELEASE}" -o jsonpath='{.items[0].metadata.name}')
            kubectl -n "${NAMESPACE}" port-forward svc/$SVC 18080:80 >/tmp/pf.log 2>&1 &
            PF_PID=$!
            trap "kill $PF_PID" EXIT

            sleep 5
            curl -sf http://127.0.0.1:18080/health
            curl -sf -X POST http://127.0.0.1:18080/predict \
              -H "Content-Type: application/json" \
              --data @payload.json
          '''
        }
      }
    }
  }
}