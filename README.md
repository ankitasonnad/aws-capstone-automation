# 🎓 AWS Cloud Infrastructure Automation: 15-Project Capstone Suite

Welcome to the **AWS Capstone Automation Suite**. This repository contains a comprehensive collection of 15 end-to-end AWS infrastructure projects, fully automated using **Python 3** and the **Boto3 SDK**.

This suite demonstrates production-ready automation for various cloud architectures, ranging from scalable web hosting and multi-tier applications to serverless processing and containerized microservices.

---

## 🛠️ Tech Stack & Prerequisites

*   **Primary Language:** Python 3.x
*   **AWS SDK:** Boto3 (Amazon Web Services SDK for Python)
*   **Infrastructure as Code:** Pure Python-based automation
*   **Containers:** Docker, Amazon ECR, Amazon ECS (Fargate)
*   **CI/CD:** AWS CodePipeline, CodeBuild
*   **Compute:** EC2, Lambda, Auto Scaling
*   **Storage & DB:** S3, RDS (MySQL)
*   **Networking:** ALB, NLB, VPC, Security Groups

### Prerequisites
1.  **AWS Credentials:** Configure your AWS CLI via `aws configure`.
2.  **Dependencies:** Install required Python libraries:
    ```bash
    pip install boto3 botocore pymysql
    ```
3.  **Local Environment:** Docker must be running for Projects 8 and 10 (Containerized apps).

---

## 📁 Repository Structure

```text
.
├── config/
│   └── aws_config.py          # Centralized AWS configuration (Region, AMI, Tags)
├── project_01_alb_autoscaling/ # High-Availability Web App with ALB
├── project_02_nlb_autoscaling/ # Performance-Focused Web App with NLB
├── project_03_multitier_webapp/ # 3-Tier Flask + RDS Deployment
├── ...                        # Projects 04 through 14
└── project_15_lambda_cicd/    # Advanced CI/CD Orchestration with Lambda
```

---

## 🚀 The Capstone Projects

| # | Project Name | Description & Innovation | Key Services |
|:---:|:---|:---|:---|
| **01** | **Scalable Web App (ALB)** | High-availability web architecture with health-monitored load balancing. | ALB, ASG, EC2 |
| **02** | **High-Performance NLB** | Low-latency architecture for high-throughput traffic using Network LB. | NLB, ASG, Nginx |
| **03** | **Multi-tier Web App** | Full-stack deployment with separate Web, App, and Database layers. | EC2, RDS, ALB |
| **04** | **Resource Provisioning** | Automated "zero-click" provisioning of IAM, S3, and EC2 resources. | IAM, S3, EC2 |
| **05** | **Static Web Hosting** | Automated SDK-driven deployment of a static website to S3. | S3, Boto3 |
| **06** | **Cost Optimizer** | Serverless Lambda logic to automatically stop idle instances & save costs. | Lambda, EventBridge |
| **07** | **Node.js CI/CD** | Full pipeline from Source (S3) to Build (CodeBuild) for Node apps. | CodePipeline, CodeBuild |
| **08** | **Flask Containerized** | Modern container deployment for Python Flask apps using Fargate. | ECR, ECS, Docker |
| **09** | **Serverless Resizer** | Event-driven image processing pipeline using S3 triggers. | Lambda, S3 |
| **10** | **Node.js Containerized** | Scalable containerized Node.js Express dashboard on Fargate. | ECR, ECS, Fargate |
| **11** | **Attendance CI/CD** | Real-world application pipeline deploying to live EC2 targets. | CodePipeline, EC2 |
| **12** | **Bus Booking App** | Comprehensive real-world app deployment with RDS data persistence. | EC2, RDS, ALB, ASG |
| **13** | **LAMP Stack Hosting** | Traditional Linux, Apache, MySQL, PHP hosting on cloud infra. | EC2, RDS, PHP |
| **14** | **LEMP Stack Hosting** | Modern, fast Linux, Nginx, MySQL, PHP-FPM web stack. | EC2, RDS, Nginx |
| **15** | **Lambda CI/CD Trigger** | Advanced orchestration triggering pipelines via serverless functions. | Lambda, CodePipeline |

---

## 🔧 Operational Guide

### Deploying a Project
Each project is self-contained. Navigate to the project directory and run the deployment script:
```bash
cd project_12_bus_booking_app
python3 deploy.py
```

### Resource Cleanup
To prevent unwanted AWS charges, every project includes a robust cleanup script:
```bash
python3 destroy.py
```

### Centralized Configuration
You can modify global parameters like the **AWS Region**, **AMI ID**, or **Key Pair Name** in [config/aws_config.py](config/aws_config.py).

---

## 🌟 Features & Highlights
*   **Pure Automation:** 100% of infrastructure is created via code; no manual Console clicks required.
*   **Premium UI:** Applications include styled, responsive dashboards (HTML/CSS) for a professional look.
*   **Idempotency:** Scripts are designed to handle existing resources gracefully.
*   **State Management:** Each project maintains a `state.json` file for tracking and cleaning up resources.

---

*This capstone suite was developed as a comprehensive demonstration of AWS Cloud Engineering and Automation capabilities.*
