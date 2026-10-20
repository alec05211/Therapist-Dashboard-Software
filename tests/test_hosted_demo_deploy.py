import shutil
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
DEPLOY_SCRIPT = PROJECT_ROOT / "deploy" / "hosted-demo" / "deploy.sh"
TERRAFORM_MAIN = PROJECT_ROOT / "terraform" / "demo-app" / "main.tf"
TERRAFORM_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "terraform-demo-app.yml"
DEPLOY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-demo-app.yml"
BOOTSTRAP_MAIN = PROJECT_ROOT / "terraform" / "bootstrap" / "main.tf"
HOME_PAGE = PROJECT_ROOT / "frontend" / "src" / "app" / "page.tsx"


class HostedDemoDeployTests(unittest.TestCase):
    def test_deploy_script_has_valid_bash_syntax(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is not installed on this platform")

        result = subprocess.run(
            [bash, "-n", str(DEPLOY_SCRIPT)],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_secret_provider_is_required_before_build_and_rollout(self):
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("dnf install -y aws-workload-credentials-provider", script)
        self.assertIn('export ASM_EXEC_REQUIRE_SMA="true"', script)
        self.assertLess(script.index("ensure_secret_provider\n"), script.index("docker build"))

    def test_candidates_are_created_before_current_containers_are_replaced(self):
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('python3 "$secret_resolver" -- docker create', script)
        self.assertLess(
            script.index('create_api "$api_image" "$api_candidate"'),
            script.index(
                "promote_container therapist-dashboard-api \"$api_candidate\""
            ),
        )
        self.assertLess(
            script.index('create_frontend "$frontend_image" "$frontend_candidate"'),
            script.index(
                "promote_container therapist-dashboard-frontend \"$frontend_candidate\""
            ),
        )

    def test_previous_release_is_kept_until_both_services_are_healthy(self):
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        frontend_promotion = script.index(
            "promote_container therapist-dashboard-frontend \"$frontend_candidate\""
        )

        self.assertGreater(
            script.index('discard_previous_container "$api_previous"'),
            frontend_promotion,
        )
        self.assertIn(
            'restore_previous_container therapist-dashboard-api "$api_previous"',
            script,
        )

    def test_instance_role_can_describe_each_allowed_secret(self):
        terraform = TERRAFORM_MAIN.read_text(encoding="utf-8")

        self.assertEqual(terraform.count('"secretsmanager:DescribeSecret"'), 3)
        self.assertEqual(terraform.count('"secretsmanager:GetSecretValue"'), 3)

    def test_terraform_workflow_preserves_organization_storage_policies(self):
        workflow = TERRAFORM_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("list-attached-role-policies", workflow)
        self.assertIn("organization_storage_policy_arns", workflow)

    def test_github_app_role_can_read_instance_type_metadata(self):
        bootstrap = BOOTSTRAP_MAIN.read_text(encoding="utf-8")

        self.assertIn('"ec2:DescribeInstanceTypes"', bootstrap)

    def test_session_aware_homepage_is_rendered_per_request(self):
        homepage = HOME_PAGE.read_text(encoding="utf-8")

        self.assertIn('export const dynamic = "force-dynamic";', homepage)
        self.assertIn("auth0.getSession()", homepage)

    def test_deployment_rejects_a_shared_cached_homepage(self):
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("x-nextjs-prerender", workflow)
        self.assertIn("s-maxage", workflow)


if __name__ == "__main__":
    unittest.main()
