pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    AWS_REGION    = "us-east-1"
    CLUSTER_NAME  = "tfm-mlops-dev"

    // ECR
    ECR_REPO      = "tfm-mlops-inference"
    IMAGE_TAG     = "0.1-${env.BUILD_NUMBER}"

    // K8s / Helm
    NAMESPACE     = "apps"
    RELEASE       = "inference"
    DEPLOYMENT    = "inference-inference"
    SERVICE       = "inference-inference"

    // Subcarpeta real del proyecto
    PROJECT_DIR   = "tfm-mlops-eks"
    CHART_DIR     = "helm/inference-service"
  }

  stages {

    stage("Checkout") {
      steps { checkout scm }
    }

    stage("Verify tools") {
      steps {
        sh '''
          set -e
          docker version
          aws --version
          kubectl version --client
          helm version
        '''
      }
    }

    stage("AWS identity + ECR login") {
      steps {
        sh '''
          set -euo pipefail

          aws sts get-caller-identity

          ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
          ECR_URI=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}

          echo "ECR_URI=$ECR_URI" > ecr.env

          # Crea repo si no existe (idempotente)
          aws ecr describe-repositories --region ${AWS_REGION} --repository-names ${ECR_REPO} >/dev/null 2>&1 \
            || aws ecr create-repository --region ${AWS_REGION} --repository-name ${ECR_REPO} >/dev/null

          aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin $ECR_URI
        '''
      }
    }

    stage("Build & Push image") {
      steps {
        dir("${PROJECT_DIR}") {
          sh '''
            set -euo pipefail
            source ../ecr.env

            docker build -t ${ECR_REPO}:${IMAGE_TAG} ./service
            docker tag  ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
            docker push ${ECR_URI}:${IMAGE_TAG}
          '''
        }
      }
    }

    stage("Update kubeconfig") {
      steps {
        sh '''
          set -euo pipefail
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER_NAME}
          kubectl get nodes
        '''
      }
    }

    stage("Helm deploy") {
      steps {
        dir("${PROJECT_DIR}") {
          sh '''
            set -euo pipefail
            source ../ecr.env

            helm lint ./${CHART_DIR}

            helm upgrade --install ${RELEASE} ./${CHART_DIR} -n ${NAMESPACE} --create-namespace \
              --set image.repository=${ECR_URI} \
              --set image.tag=${IMAGE_TAG}

            kubectl -n ${NAMESPACE} rollout status deploy/${DEPLOYMENT} --timeout=180s
            kubectl -n ${NAMESPACE} get pods
          '''
        }
      }
    }

    stage("Smoke test (in-cluster)") {
      steps {
        sh '''
          set -euo pipefail

          # kubectl de tu versión requiere "attach" para permitir --rm
          kubectl -n ${NAMESPACE} run smoke-${BUILD_NUMBER} --rm --restart=Never --image=curlimages/curl --attach -- \
            curl -fsS http://${SERVICE}/health

          kubectl -n ${NAMESPACE} run smoke2-${BUILD_NUMBER} --rm --restart=Never --image=curlimages/curl --attach -- \
            curl -fsS -X POST http://${SERVICE}/predict \
              -H "Content-Type: application/json" \
              -d '{"features":{"laufkont":2,"laufzeit":24,"moral":2,"verw":3,"hoehe":2000,"sparkont":2,"beszeit":2,"rate":2,"famges":2,"buerge":1,"wohnzeit":2,"verm":2,"alter":35,"weitkred":1,"wohn":2,"bishkred":1,"beruf":3,"pers":1,"telef":1,"gastarb":1}}'
        '''
      }
    }
  }

  post {
    always {
      sh 'echo "Pipeline finished. Build=${BUILD_NUMBER}"'
    }
  }
}