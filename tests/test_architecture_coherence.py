from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.blueprint import SYSTEM_BLUEPRINT  # noqa: E402
from klone.config import Settings  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.services import ServiceContainer  # noqa: E402


class ArchitectureCoherenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_public_capability_catalog_maps_to_routes_and_known_seams(self) -> None:
        app = create_app(self._settings_for("architecture_coherence.sqlite"))
        repository = KloneRepository(self.root / "architecture_coherence.sqlite")
        repository.initialize()
        services = ServiceContainer.build(repository)

        route_methods = {
            (route.path, method)
            for route in app.routes
            for method in getattr(route, "methods", set())
        }
        seam_names = {descriptor.name for descriptor in services.seam_descriptors()}
        capabilities = services.public_capabilities()

        capability_ids = [capability.id for capability in capabilities]
        self.assertEqual(len(capability_ids), len(set(capability_ids)))
        self.assertGreater(len(capabilities), 0)

        for capability in capabilities:
            self.assertTrue(capability.methods, msg=f"{capability.id} must declare at least one method.")
            self.assertTrue(capability.path.startswith("/"), msg=f"{capability.id} path must be absolute.")
            self.assertTrue(capability.description.strip(), msg=f"{capability.id} must describe itself.")
            self.assertTrue(capability.backed_by, msg=f"{capability.id} must name its backing seams.")

            for method in capability.methods:
                self.assertEqual(
                    method,
                    method.upper(),
                    msg=f"{capability.id} declared a non-uppercase HTTP method: {method}",
                )
                self.assertIn(
                    (capability.path, method),
                    route_methods,
                    msg=f"{capability.id} points to missing route {method} {capability.path}",
                )

            unknown_seams = sorted(set(capability.backed_by) - seam_names)
            self.assertEqual(
                unknown_seams,
                [],
                msg=f"{capability.id} references unknown seams: {unknown_seams}",
            )

            if capability.path.startswith("/v1/"):
                self.assertTrue(
                    capability.read_only,
                    msg=f"{capability.id} must remain read-only while it lives on the public /v1 seam.",
                )

            if not capability.read_only:
                combined_text = f"{capability.status} {capability.description}".lower()
                self.assertTrue(
                    "local" in combined_text or "bounded" in combined_text,
                    msg=f"{capability.id} must declare its local or bounded write posture explicitly.",
                )

        referenced_seams = {name for capability in capabilities for name in capability.backed_by}
        missing_from_catalog = sorted(seam_names - referenced_seams)
        self.assertEqual(
            missing_from_catalog,
            [],
            msg=f"Every seam should be visible through at least one public capability: {missing_from_catalog}",
        )

    def test_blueprint_metadata_stays_unique_and_grounded_in_trust_zones(self) -> None:
        trust_zone_ids = [zone.id for zone in SYSTEM_BLUEPRINT.trust_zones]
        module_ids = [module.id for module in SYSTEM_BLUEPRINT.modules]
        phase_ids = [phase.id for phase in SYSTEM_BLUEPRINT.build_phases]

        self.assertEqual(len(trust_zone_ids), len(set(trust_zone_ids)))
        self.assertEqual(len(module_ids), len(set(module_ids)))
        self.assertEqual(len(phase_ids), len(set(phase_ids)))

        for zone in SYSTEM_BLUEPRINT.trust_zones:
            self.assertTrue(zone.name.strip())
            self.assertTrue(zone.description.strip())
            self.assertTrue(zone.examples)

        for module in SYSTEM_BLUEPRINT.modules:
            self.assertIn(module.zone_id, trust_zone_ids, msg=f"{module.id} points to an unknown trust zone.")
            self.assertTrue(module.name.strip())
            self.assertTrue(module.supervisor.strip())
            self.assertTrue(module.stage.strip())
            self.assertTrue(module.status.strip())
            self.assertTrue(module.purpose.strip())
            self.assertTrue(module.key_inputs, msg=f"{module.id} should list its inputs.")
            self.assertTrue(module.outputs, msg=f"{module.id} should list its outputs.")

        for phase in SYSTEM_BLUEPRINT.build_phases:
            self.assertTrue(phase.title.strip())
            self.assertTrue(phase.goal.strip())
            self.assertTrue(phase.deliverables, msg=f"{phase.id} should list concrete deliverables.")

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Architecture Coherence Test",
            environment="test",
            owner_debug_mode=True,
            project_root=PROJECT_ROOT,
            data_dir=self.root / "data",
            sqlite_path=database_path,
            asset_preview_limit=12,
            audit_preview_limit=9,
        )


if __name__ == "__main__":
    unittest.main()
