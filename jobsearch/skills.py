"""Skill dictionary: canonical names, the ways people write them, and how to find them in text.

Each entry is  "Canonical": [aliases...]  and optionally a mode:
    "ci"  - case-insensitive whole-word match anywhere (default)
    "cs"  - case-sensitive whole-word match (for words that are also plain English)
    "tag" - only from explicit skill lists (job skill tags, a resume's skills section), never free text
Add skills freely; matching picks them up everywhere.
"""
import re

SKILLS = {
    # Cloud
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Oracle Cloud": ["oci", "oracle cloud"],
    "EC2": ["ec2"],
    "S3": ["s3"],
    "IAM": ["iam"],
    "VPC": ["vpc"],
    "RDS": ["rds"],
    "ELB": ["elb", "alb", "elastic load balancer"],
    "Auto Scaling": ["auto scaling", "autoscaling", "auto-scaling"],
    "Route53": ["route53", "route 53"],
    "Lambda": ["aws lambda", "lambda functions"],
    "CloudFormation": ["cloudformation", "cloud formation"],
    "CloudWatch": ["cloudwatch", "cloud watch"],
    "EKS": ["eks", "amazon eks"],
    "ECS": ["ecs", "fargate"],
    "AKS": ["aks"],
    "GKE": ["gke"],
    "OpenShift": ["openshift"],
    "PCF": ["pcf", "pivotal cloud foundry", "cloud foundry"],
    "Serverless": ["serverless"],
    # DevOps / platform
    "DevOps": ["devops"],
    "CI/CD": ["ci/cd", "ci cd", "cicd", "ci-cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "Jenkins": ["jenkins"],
    "GitLab": ["gitlab", "gitlab ci", "gitlab-ci", "gitlab ci/cd"],
    "GitHub Actions": ["github actions"],
    "Azure DevOps": ["azure devops", "azure pipelines", "vsts"],
    "CircleCI": ["circleci", "circle ci"],
    "ArgoCD": ["argocd", "argo cd", "argo"],
    "GitOps": ["gitops"],
    "AWS CodePipeline": ["codepipeline", "code pipeline", "codebuild", "codedeploy"],
    "Terraform": ["terraform"],
    "Pulumi": ["pulumi"],
    "Infrastructure as Code": ["infrastructure as code", "iac"],
    "Ansible": ["ansible"],
    "Chef": ["chef"],
    "Puppet": ["puppet"],
    "Packer": ["packer"],
    "Docker": ["docker", "containerization", "containerisation"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Helm": ["helm", "helm charts"],
    "Istio": ["istio", "service mesh", "linkerd"],
    "Linux": ["linux", "rhel", "centos", "ubuntu", "red hat"],
    "Unix": ["unix"],
    "Shell Scripting": ["shell scripting", "shell script", "shell scripts", "bash", "shell"],
    "PowerShell": ["powershell"],
    "Nginx": ["nginx"],
    "Apache": ["apache httpd", "apache web server", "apache"],
    "Tomcat": ["tomcat"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "ELK Stack": ["elk", "elk stack", "elasticsearch", "logstash", "kibana", "opensearch"],
    "Splunk": ["splunk"],
    "Datadog": ["datadog"],
    "New Relic": ["new relic", "newrelic"],
    "Dynatrace": ["dynatrace"],
    "AppDynamics": ["appdynamics"],
    "Nagios": ["nagios"],
    "Zabbix": ["zabbix"],
    "OpenTelemetry": ["opentelemetry", "otel"],
    "Observability": ["observability"],
    "Monitoring": ["monitoring"],
    "ServiceNow": ["servicenow", "service now"],
    "Jira": ["jira"],
    "SonarQube": ["sonarqube", "sonar"],
    "Nexus": ["nexus repository", "sonatype nexus"],
    "Artifactory": ["artifactory", "jfrog"],
    "Maven": ["maven"],
    "Gradle": ["gradle"],
    "Vault": ["hashicorp vault", "vault"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Redis": ["redis"],
    "Git": ["git"],
    "GitHub": ["github"],
    "Bitbucket": ["bitbucket"],
    "DNS": ["dns"],
    "TCP/IP": ["tcp/ip", "tcp ip"],
    "Load Balancing": ["load balancing", "load balancer", "load balancers"],
    "Networking": ["networking", "computer networks"],
    "Incident Management": ["incident management", "incident response", "on-call", "on call"],
    "RCA": ["rca", "root cause analysis"],
    "SRE": ["sre", "site reliability"],
    "Microservices": ["microservices", "micro services", "micro-services"],
    "DevSecOps": ["devsecops"],
    "Security Scanning": ["sast", "dast", "trivy", "snyk", "checkmarx", "veracode"],
    "VMware": ["vmware", "vsphere"],
    "Windows Server": ["windows server"],
    "Active Directory": ["active directory"],
    # Languages
    "Python": ["python"],
    "Java": ["java", "core java", "j2ee"],
    "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript"],
    "Go": (["golang", "go"], "tag"),
    "Rust": (["rust"], "cs"),
    "C": (["c"], "tag"),
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    ".NET": [".net", "dotnet", "asp.net", ".net core"],
    "Ruby": (["ruby"], "cs"),
    "PHP": ["php"],
    "Scala": ["scala"],
    "Kotlin": ["kotlin"],
    "Swift": (["swift"], "cs"),
    "R": (["r"], "tag"),
    "Perl": ["perl"],
    "Groovy": ["groovy"],
    "SQL": ["sql"],
    "PL/SQL": ["pl/sql", "plsql"],
    "NoSQL": ["nosql"],
    "Dart": (["dart"], "cs"),
    "YAML": ["yaml"],
    # Web
    "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular", "angularjs"],
    "Vue": ["vue", "vuejs", "vue.js"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Express": (["express.js", "expressjs", "Express"], "cs"),
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "Hibernate": ["hibernate"],
    "Ruby on Rails": ["ruby on rails", "rails"],
    "Laravel": ["laravel"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "scss", "sass"],
    "Tailwind": ["tailwind", "tailwindcss"],
    "Redux": ["redux"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest api", "rest apis", "restful", "rest"],
    "gRPC": ["grpc"],
    # Data / AI
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Oracle DB": ["oracle database", "oracle db"],
    "SQL Server": ["sql server", "mssql"],
    "Cassandra": ["cassandra"],
    "DynamoDB": ["dynamodb"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery"],
    "Redshift": ["redshift"],
    "Databricks": ["databricks"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Hadoop": ["hadoop", "hdfs", "hive"],
    "Airflow": ["airflow"],
    "dbt": ["dbt"],
    "ETL": ["etl", "elt"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": (["advanced excel", "ms excel", "microsoft excel", "Excel"], "cs"),
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "opencv"],
    "Generative AI": ["generative ai", "genai", "gen ai", "llm", "llms", "large language models"],
    "MLOps": ["mlops", "kubeflow", "mlflow"],
    "AI/ML Infra": ["gpu", "nvidia", "ai infrastructure", "ml infrastructure"],
    "Statistics": ["statistics", "statistical"],
    # Mobile
    "Android": ["android"],
    "iOS": ["ios"],
    "React Native": ["react native"],
    "Flutter": ["flutter"],
    # Testing
    "Selenium": ["selenium"],
    "Cypress": ["cypress"],
    "Playwright": ["playwright"],
    "JUnit": ["junit"],
    "PyTest": ["pytest"],
    "TestNG": ["testng"],
    "Appium": ["appium"],
    "Postman": ["postman"],
    "JMeter": ["jmeter"],
    "Automation Testing": ["automation testing", "test automation"],
    "Manual Testing": ["manual testing"],
    # Ways of working / other
    "Agile": ["agile", "scrum", "kanban"],
    "SAP": (["sap"], "cs"),
    "Salesforce": ["salesforce"],
    "Figma": ["figma"],
}

# A skill on a resume that implies others (EKS on a resume means you know Kubernetes and AWS).
IMPLIES = {
    "EKS": ["Kubernetes", "AWS"], "AKS": ["Kubernetes", "Azure"], "GKE": ["Kubernetes", "GCP"],
    "OpenShift": ["Kubernetes"], "ECS": ["Docker", "AWS"], "Helm": ["Kubernetes"],
    "EC2": ["AWS"], "S3": ["AWS"], "RDS": ["AWS"], "VPC": ["AWS"], "Route53": ["AWS"], "CloudWatch": ["AWS", "Monitoring"],
    "CloudFormation": ["AWS", "Infrastructure as Code"], "Terraform": ["Infrastructure as Code"], "Pulumi": ["Infrastructure as Code"],
    "Jenkins": ["CI/CD"], "GitLab": ["CI/CD", "Git"], "GitHub Actions": ["CI/CD", "GitHub"], "Azure DevOps": ["CI/CD"],
    "AWS CodePipeline": ["CI/CD", "AWS"], "ArgoCD": ["GitOps", "CI/CD"], "GitHub": ["Git"], "Bitbucket": ["Git"],
    "Prometheus": ["Monitoring"], "Grafana": ["Monitoring"], "Datadog": ["Monitoring"], "ELK Stack": ["Monitoring"],
    "Splunk": ["Monitoring"], "New Relic": ["Monitoring"], "Dynatrace": ["Monitoring"],
    "Next.js": ["React", "JavaScript"], "React": ["JavaScript"], "Angular": ["TypeScript"], "Node.js": ["JavaScript"],
    "TypeScript": ["JavaScript"], "Spring Boot": ["Java"], "Django": ["Python"], "Flask": ["Python"], "FastAPI": ["Python"],
    "PostgreSQL": ["SQL"], "MySQL": ["SQL"], "SQL Server": ["SQL"], "PL/SQL": ["SQL"],
    "Pandas": ["Python"], "PyTorch": ["Machine Learning"], "TensorFlow": ["Machine Learning"], "scikit-learn": ["Machine Learning"],
    "SonarQube": ["Security Scanning"], "DevSecOps": ["DevOps"], "SRE": ["DevOps"],
}

# Skills too generic to count as a "gap" when a job mentions them and you don't list them.
SOFT_GAPS = {"Monitoring", "Networking", "Agile", "Observability", "DevOps", "Excel", "Infrastructure as Code"}

_SEP = r"(?<![A-Za-z0-9+#])"
_END = r"(?![A-Za-z0-9+#])"


def _compile():
    table = []
    for name, spec in SKILLS.items():
        aliases, mode = (spec if isinstance(spec, tuple) else (spec, "ci"))
        aliases = sorted({a for a in aliases} | {name}, key=len, reverse=True)
        if mode == "tag":
            table.append((name, mode, None, {a.lower() for a in aliases}))
            continue
        alt = "|".join(re.escape(a).replace(r"\ ", r"\s+") for a in aliases)
        flags = 0 if mode == "cs" else re.IGNORECASE
        table.append((name, mode, re.compile(f"{_SEP}(?:{alt}){_END}", flags), {a.lower() for a in aliases}))
    return table


_TABLE = _compile()
_LOOKUP = {}
for _name, _mode, _rx, _aliases in _TABLE:
    for _a in _aliases:
        _LOOKUP.setdefault(_a, _name)


def canonical(tag):
    """'k8s' -> 'Kubernetes'; unknown tags come back title-cased as they are."""
    t = re.sub(r"\s+", " ", str(tag or "")).strip()
    if not t:
        return None
    return _LOOKUP.get(t.lower()) or _LOOKUP.get(re.sub(r"[^a-z0-9+#./ ]", "", t.lower()))


def find_in_text(text, tag_context=False):
    """Skills mentioned in free text, in order of first appearance.

    tag_context=True also finds tag-only skills (Go, C, R) when they sit in a list such as
    'Python, Go, Java' - used for a resume's skills section."""
    text = text or ""
    found = {}
    for name, mode, rx, aliases in _TABLE:
        if rx is not None:
            m = rx.search(text)
            if m:
                found[name] = m.start()
        elif tag_context:
            alt = "|".join(re.escape(a) for a in aliases)
            m = re.search(rf"(?:^|[,|:;/•(\n])\s*(?:{alt})\s*(?=[,|;/)\n]|$)", text, re.IGNORECASE | re.MULTILINE)
            if m:
                found[name] = m.start()
    return [n for n, _ in sorted(found.items(), key=lambda kv: kv[1])]


def from_tags(tags):
    """Canonical skills from a list of tags; unknown tags are kept as typed (so they still show as gaps)."""
    out = []
    for t in tags or []:
        if isinstance(t, dict):
            t = t.get("label") or t.get("name") or ""
        c = canonical(t)
        if c is None:
            hits = find_in_text(str(t))
            out.extend(hits)
        else:
            out.append(c)
    return list(dict.fromkeys(out))


def expand(skills):
    """Add what each skill implies (EKS -> Kubernetes, AWS)."""
    out = list(dict.fromkeys(skills))
    seen = set(out)
    i = 0
    while i < len(out):
        for extra in IMPLIES.get(out[i], []):
            if extra not in seen:
                seen.add(extra)
                out.append(extra)
        i += 1
    return out
