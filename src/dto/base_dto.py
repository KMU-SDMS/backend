"""
기본 DTO 클래스들을 정의합니다.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class BaseDTO:
    """모든 DTO의 기본 클래스"""
    
    def to_dict(self) -> Dict[str, Any]:
        """DTO를 딕셔너리로 변환"""
        return asdict(self)
    
    def to_json(self) -> str:
        """DTO를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseDTO':
        """딕셔너리에서 DTO 생성"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BaseDTO':
        """JSON 문자열에서 DTO 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class ErrorDTO(BaseDTO):
    """에러 응답 DTO"""
    error: str
    status_code: int = 500
    
    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.error}


@dataclass
class SuccessDTO(BaseDTO):
    """성공 응답 DTO"""
    data: Any
    status_code: int = 200
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data
