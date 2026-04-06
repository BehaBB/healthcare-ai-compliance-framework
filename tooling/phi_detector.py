# tooling/phi_detector.py
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import spacy
from typing import Dict, List, Any, Tuple

class PresidioPHIDetector:
    """
    Профессиональный детектор PHI с использованием Microsoft Presidio
    Поддерживает 8+ типов PHI + кастомные медицинские паттерны
    """
    
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.nlp = spacy.load("en_core_web_lg")
        
        # Добавляем поддержку медицинских терминов
        self.medical_keywords = [
            "diabetes", "hypertension", "insulin", "metformin", "cancer", 
            "chemotherapy", "mri", "ct scan", "patient record", "medical history"
        ]

    def detect_phi(self, text: str) -> Dict[str, Any]:
        """Основная функция: обнаруживает PHI и возвращает детальную информацию"""
        if not text or not text.strip():
            return {"phi_found": False, "entities": [], "risk_level": "low"}

        # Анализ через Presidio
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "DATE_TIME", 
                     "US_SSN", "US_DRIVER_LICENSE", "IP_ADDRESS"]
        )

        # Дополнительная проверка медицинских терминов
        doc = self.nlp(text.lower())
        medical_entities = []
        for token in doc:
            if any(keyword in token.text for keyword in self.medical_keywords):
                medical_entities.append({
                    "entity_type": "MEDICAL_TERM",
                    "start": token.idx,
                    "end": token.idx + len(token.text),
                    "score": 0.85
                })

        all_entities = results + medical_entities
        
        phi_found = len(all_entities) > 0
        risk_level = self._calculate_risk_level(all_entities)

        return {
            "phi_found": phi_found,
            "entities": [
                {
                    "entity_type": entity.entity_type if hasattr(entity, 'entity_type') else entity.get("entity_type"),
                    "start": entity.start if hasattr(entity, 'start') else entity.get("start"),
                    "end": entity.end if hasattr(entity, 'end') else entity.get("end"),
                    "score": float(entity.score) if hasattr(entity, 'score') else entity.get("score", 0.8)
                }
                for entity in all_entities
            ],
            "risk_level": risk_level,
            "phi_count": len(all_entities)
        }

    def anonymize_text(self, text: str) -> Tuple[str, Dict]:
        """Анонимизирует текст (заменяет PHI на [REDACTED])"""
        if not text:
            return text, {}

        analyzer_results = self.analyzer.analyze(text=text, language="en")
        
        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})},
        )
        
        return anonymized.text, {
            "original_length": len(text),
            "anonymized_length": len(anonymized.text),
            "entities_redacted": len(analyzer_results)
        }

    def _calculate_risk_level(self, entities: List) -> str:
        """Простая система оценки риска"""
        if len(entities) >= 3:
            return "high"
        elif len(entities) >= 1:
            return "medium"
        return "low"

# Fallback детектор (если Presidio не работает)
def simple_phi_check(text: str) -> bool:
    """Простая резервная проверка"""
    import re
    patterns = [r"\b\d{3}-\d{2}-\d{4}\b", r"\bpatient\b", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"]
    return any(re.search(p, text.lower()) for p in patterns)