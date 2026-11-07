"""Offline safety invariants; the integration suite tests a real API server."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = load("render").render
matches = load("check_access").decision_matches


class PolicyTests(unittest.TestCase):
    def test_scoped_objects_and_group(self):
        for group in ("platform-readers", "00000000-0000-0000-0000-000000000001", "readers@example.com"):
            namespace, role, binding = render(group, "review-team")
            self.assertEqual([namespace["kind"], role["kind"], binding["kind"]], ["Namespace", "Role", "RoleBinding"])
            self.assertEqual(namespace["metadata"]["name"], "review-team")
            self.assertEqual(role["metadata"]["namespace"], "review-team")
            self.assertEqual(binding["metadata"]["namespace"], "review-team")
            self.assertEqual(binding["subjects"], [{"kind":"Group", "name":group, "apiGroup":"rbac.authorization.k8s.io"}])
            self.assertEqual(binding["roleRef"]["kind"], "Role")
            self.assertEqual(binding["roleRef"]["name"], role["metadata"]["name"])

    def test_no_mutation_wildcards_or_sensitive_resources(self):
        role = render("readers")[1]
        allowed_resources = {"pods", "pods/log", "services", "events", "deployments", "replicasets"}
        for rule in role["rules"]:
            self.assertLessEqual(set(rule["verbs"]), {"get", "list", "watch"})
            self.assertLessEqual(set(rule["resources"]), allowed_resources)
            self.assertLessEqual(set(rule["apiGroups"]), {"", "apps"})
            self.assertNotIn("nonResourceURLs", rule)

    def test_reserved_and_malformed_names_rejected(self):
        for group in ("", "system:masters", " readers", "readers\n---\nkind: ClusterRoleBinding"):
            with self.subTest(group=group), self.assertRaises(ValueError):
                render(group)
        for namespace in ("UPPER", "-invalid", "a" * 64, "team/a"):
            with self.subTest(namespace=namespace), self.assertRaises(ValueError):
                render("readers", namespace)

    def test_network_and_authentication_errors_are_not_expected_denials(self):
        for output, error, code in (("", "connection refused", 1), ("", "Unauthorized", 1), ("no", "", 0), ("yes", "", 0)):
            self.assertFalse(matches(subprocess.CompletedProcess([], code, output, error), False))
        self.assertTrue(matches(subprocess.CompletedProcess([], 1, "no\n", ""), False))
        self.assertTrue(matches(subprocess.CompletedProcess([], 0, "yes\n", ""), True))


if __name__ == "__main__":
    unittest.main()
