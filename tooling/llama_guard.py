# tooling/llama_guard.py
import re
from typing import Dict, List, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class LlamaGuard:
    """
    Llama Guard 3 - Safety guardrail для медицинских AI систем
    Проверяет промпты на unsafe контент, jailbreak атаки и медицинские риски
    """
    
    # Категории unsafe контента по стандарту Meta
    UNSAFE_CATEGORIES = {
        "S1": "Violent Crimes",
        "S2": "Non-Violent Crimes", 
        "S3": "Sex-Related Crimes",
        "S4": "Child Sexual Exploitation",
        "S5": "Defamation",
        "S6": "Specialized Advice",
        "S7": "Privacy",
        "S8": "Intellectual Property",
        "S9": "Indiscriminate Weapons",
        "S10": "Hate",
        "S11": "Self-Harm",
        "S12": "Sexual Content",
        "S13": "Elections",
        "S14": "Code Interpreter Abuse"
    }
    
    # Медицинские unsafe паттерны
    MEDICAL_UNSAFE_PATTERNS = {
        "jailbreak": [
            r"ignore (?:previous|all|your) (?:instructions|prompts|rules|guidelines)",
            r"act as (?:a|an) (?:doctor|physician|medical professional|healthcare provider)",
            r"pretend (?:you are|to be) (?:a|an) (?:doctor|physician)",
            r"bypass (?:safety|security|restrictions|guardrails)",
            r"do not (?:follow|obey|comply with) (?:your|the) (?:safety|guidelines|rules)",
            r"you are now (?:in|under) (?:jailbreak|developer mode)",
            r"no (?:safety|guardrails|restrictions|limits)"
        ],
        "medical_risk": [
            r"how to (?:make|create|synthesize) (?:drugs|medication|medicine) (?:at home|illegally)",
            r"overdose on (?:medication|pills|drugs|insulin|metformin)",
            r"how to (?:harm|hurt|kill) (?:yourself|myself|someone) with (?:medication|drugs)",
            r"prescribe (?:me|yourself) (?:medication|drugs) without (?:doctor|prescription)",
            r"treat (?:cancer|serious illness|critical condition) with (?:home remedies|alternative medicine only)",
            r"stop taking prescribed (?:medication|drugs|insulin) immediately"
        ],
        "phi_request": [
            r"share (?:patient|medical) (?:records|history|information|data)",
            r"give me (?:my|a patient's) (?:medical history|health records|treatment plan)",
            r"access (?:phi|protected health information) without authorization"
        ]
    }
    
    def __init__(self):
        # Компилируем регулярные выражения
        self.patterns = {}
        for category, patterns in self.MEDICAL_UNSAFE_PATTERNS.items():
            self.patterns[category] = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        logger.info("Llama Guard initialized with medical safety rules")
    
    def check(self, text: str) -> Dict[str, Any]:
        """
        Проверяет текст на unsafe контент
        Возвращает: {
            "safe": bool,
            "violations": list,
            "categories": list,
            "risk_level": str
        }
        """
        if not text or not text.strip():
            return {
                "safe": True,
                "violations": [],
                "categories": [],
                "risk_level": "low"
            }
        
        violations = []
        categories = []
        
        # Проверка по категориям
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    violations.append({
                        "category": category,
                        "pattern": pattern.pattern,
                        "matches": matches[:3]  # первые 3 совпадения
                    })
                    categories.append(category)
                    break  # достаточно одного срабатывания на категорию
        
        # Определяем уровень риска
        if "jailbreak" in categories:
            risk_level = "critical"
        elif "medical_risk" in categories:
            risk_level = "high"
        elif "phi_request" in categories:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        is_safe = len(violations) == 0
        
        return {
            "safe": is_safe,
            "violations": violations,
            "categories": list(set(categories)),
            "risk_level": risk_level,
            "message": self._get_safety_message(is_safe, categories)
        }
    
    def _get_safety_message(self, is_safe: bool, categories: list) -> str:
        """Возвращает человеко-читаемое сообщение о безопасности"""
        if is_safe:
            return "Content passed safety check"
        
        if "jailbreak" in categories:
            return "BLOCKED: Jailbreak attempt detected - trying to bypass safety guidelines"
        elif "medical_risk" in categories:
            return "BLOCKED: Unsafe medical content detected - potentially harmful instructions"
        elif "phi_request" in categories:
            return "BLOCKED: Unauthorized PHI access request"
        
        return "BLOCKED: Content violates safety policies"
    
    def quick_check(self, text: str) -> Tuple[bool, str]:
        """
        Быстрая проверка (только safe/unsafe с кратким сообщением)
        """
        result = self.check(text)
        return result["safe"], result["message"]


# Легковесный fallback (если Llama Guard недоступен)
class SimpleGuard:
    """Простая fallback проверка без ML"""
    
    def check(self, text: str) -> Dict[str, Any]:
        dangerous_keywords = [
            "ignore instructions", "jailbreak", "bypass safety",
            "how to make meth", "overdose", "suicide", "self-harm"
        ]
        
        text_lower = text.lower()
        violations = [kw for kw in dangerous_keywords if kw in text_lower]
        
        return {
            "safe": len(violations) == 0,
            "violations": violations,
            "categories": ["blocked_keywords"] if violations else [],
            "risk_level": "high" if violations else "low"
        }