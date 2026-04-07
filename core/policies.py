# core/policies.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import json
import hashlib
from pathlib import Path

import yaml  # pip install pyyaml

class PolicySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PolicyRule:
    type: str                    # phi_detection, llama_guard, medical_recommendation, prompt_injection и т.д.
    action: str                  # block, redact, review, warn, allow
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass
class Policy:
    id: str
    name: str
    version: str
    description: str
    severity: PolicySeverity
    enabled: bool = True
    category: str = "general"          # new: phi, safety, medical, operational
    created_at: datetime = field(default_factory=datetime.utcnow)
    modified_at: datetime = field(default_factory=datetime.utcnow)
    rules: List[PolicyRule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "rules": [rule.__dict__ for rule in self.rules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        rules = [PolicyRule(**r) for r in data.get("rules", [])]
        severity = PolicySeverity(data["severity"])
        return cls(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            description=data["description"],
            severity=severity,
            enabled=data.get("enabled", True),
            category=data.get("category", "general"),
            rules=rules
        )


class PolicyManager:
    """Централизованное управление политиками compliance с поддержкой файлов"""

    def __init__(self, policies_dir: str = "policies"):
        self.policies_dir = Path(policies_dir)
        self.policies_dir.mkdir(exist_ok=True, parents=True)
        self.policies: Dict[str, Policy] = {}
        self._load_all_policies()

    def _load_all_policies(self):
        """Загружает все политики из YAML/JSON файлов + дефолтные"""
        self.policies.clear()

        # Загружаем из файлов (приоритет выше)
        for file in self.policies_dir.glob("*.yaml"):
            try:
                with open(file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "id" in data:
                        policy = Policy.from_dict(data)
                        self.policies[policy.id] = policy
            except Exception as e:
                print(f"Warning: Failed to load policy {file}: {e}")

        # Если нет ни одной политики — создаём дефолтные
        if not self.policies:
            self._create_default_policies()
            self._save_all_policies()

    def _create_default_policies(self):
        """Создаёт мощные дефолтные политики для healthcare AI"""

        default_policies = [
            Policy(
                id="POL-001",
                name="PHI Protection Policy",
                version="2.0.0",
                description="Strict protection of Protected Health Information (HIPAA)",
                severity=PolicySeverity.HIGH,
                category="phi",
                rules=[
                    PolicyRule(
                        type="phi_detection",
                        action="redact",
                        parameters={"entities": ["PERSON", "DATE", "LOCATION", "MEDICAL_RECORD"]},
                        description="Redact common PHI entities"
                    ),
                    PolicyRule(
                        type="phi_detection",
                        action="block",
                        parameters={"entities": ["US_SSN", "DRIVER_LICENSE", "EMAIL"]},
                        description="Block highly sensitive identifiers"
                    )
                ]
            ),
            Policy(
                id="POL-002",
                name="Content Safety & Jailbreak Protection",
                version="2.0.0",
                description="Uses Llama Guard 3 / NeMo to block unsafe and adversarial prompts",
                severity=PolicySeverity.CRITICAL,
                category="safety",
                rules=[
                    PolicyRule(
                        type="llama_guard",
                        action="block",
                        parameters={"categories": ["jailbreak", "violence", "self_harm", "sexual"]},
                    )
                ]
            ),
            Policy(
                id="POL-003",
                name="Medical Advice Compliance Policy",
                version="2.0.0",
                description="Prevents unauthorized clinical recommendations (FDA + liability)",
                severity=PolicySeverity.HIGH,
                category="medical",
                rules=[
                    PolicyRule(
                        type="medical_recommendation",
                        action="require_human_review",
                        parameters={
                            "keywords": ["recommend", "prescribe", "treat", "dosage", "metformin", "insulin"],
                            "confidence_threshold": 0.75,
                            "disclaimer_required": True
                        },
                        description="Any drug or treatment recommendation requires human review"
                    ),
                    PolicyRule(
                        type="diagnosis",
                        action="block",
                        parameters={"confidence_threshold": 0.8},
                        description="Block direct diagnosis without physician"
                    )
                ]
            ),
            Policy(
                id="POL-004",
                name="Prompt Injection Protection",
                version="1.1.0",
                description="Detects and blocks prompt injection attempts",
                severity=PolicySeverity.CRITICAL,
                category="safety",
                rules=[
                    PolicyRule(type="prompt_injection", action="block")
                ]
            )
        ]

        for policy in default_policies:
            self.policies[policy.id] = policy

    def _save_all_policies(self):
        """Сохраняет все политики в YAML файлы"""
        for policy in self.policies.values():
            file_path = self.policies_dir / f"{policy.id}_{policy.name.lower().replace(' ', '_')}.yaml"
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(policy.to_dict(), f, sort_keys=False, allow_unicode=True)

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self.policies.get(policy_id)

    def get_policies_by_category(self, category: str) -> List[Policy]:
        return [p for p in self.policies.values() if p.category == category]

    def get_enabled_policies(self) -> List[Policy]:
        return [p for p in self.policies.values() if p.enabled]

    def get_policy_hash(self) -> str:
        """Хеш всех политик — удобно для аудита и кэширования"""
        policies_list = [p.to_dict() for p in sorted(self.policies.values(), key=lambda x: x.id)]
        policies_str = json.dumps(policies_list, sort_keys=True)
        return hashlib.sha256(policies_str.encode()).hexdigest()[:12]

    def reload_policies(self):
        """Перезагружает политики из файлов (для hot-reload)"""
        self._load_all_policies()