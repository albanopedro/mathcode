"""POST /api/calculate through real worker processes."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.api.calculate import MAX_REQUEST_INPUT_LENGTH
from app.core.limits import MAX_INPUT_LENGTH
from app.models.result import MathResult


def post(api: TestClient, body: object) -> tuple[int, dict]:
    response = api.post("/api/calculate", json=body)
    return response.status_code, response.json()


def test_solves_an_equation(api: TestClient) -> None:
    status, data = post(api, {"input": "2x + 5 = 17"})

    assert status == 200
    result = MathResult.model_validate(data)  # the body is a valid MathResult
    assert result.success
    assert result.intent == "solve_equation"
    assert result.result is not None and result.result.plain == "x = 6"
    assert result.verification is not None
    assert result.verification.status == "verified_symbolic"


def test_json_shape(api: TestClient) -> None:
    _, data = post(api, {"input": "0.1 + 0.2"})
    assert set(data) == {
        "success",
        "intent",
        "input",
        "normalized_input",
        "result",
        "steps",
        "details",
        "verification",
        "warnings",
        "error",
    }
    assert data["result"] == {"plain": "3/10", "latex": r"\frac{3}{10}", "approx": "0.3"}
    assert data["verification"]["status"] == "verified_numeric"


def test_explicit_intent(api: TestClient) -> None:
    status, data = post(api, {"input": "x + x", "intent": "simplify"})
    assert status == 200
    assert data["intent"] == "simplify"
    assert data["result"]["plain"] == "2*x"


@pytest.mark.parametrize(
    ("text", "intent", "plain"),
    [
        ("x^2 - 4", "factor", "(x - 2)*(x + 2)"),
        ("(x + 1)^2", "expand", "x^2 + 2*x + 1"),
        ("(x^3 - 1)/(x - 1)", "polynomial_division", "quociente: x^2 + x + 1; resto: 0"),
        ("x + y = 3; x - y = 1", "solve_system", "x = 2; y = 1"),
    ],
)
def test_phase_5_intents(api: TestClient, text: str, intent: str, plain: str) -> None:
    status, data = post(api, {"input": text, "intent": intent})
    assert status == 200
    assert data["result"]["plain"] == plain


def test_options_reach_the_engine(api: TestClient) -> None:
    status, data = post(
        api, {"input": "x^2", "intent": "integral", "options": {"lower": "0", "upper": "1"}}
    )
    assert status == 200
    assert data["result"]["plain"] == "1/3"
    assert data["details"]["definite"] is True


def test_invalid_option_values_are_answers(api: TestClient) -> None:
    status, data = post(api, {"input": "x^2", "intent": "derivative", "options": {"order": 50}})
    assert status == 200
    assert data["error"]["code"] == "INVALID_INPUT_FOR_INTENT"


@pytest.mark.parametrize(
    "options",
    [
        {"order": [1]},  # not a text or a number
        {"point": "1" * 101},  # too long (and must not become a huge int)
        {"order": 10**6},  # number out of range
        {f"k{n}": "x" for n in range(9)},  # too many
    ],
)
def test_malformed_options_are_422(api: TestClient, options: dict) -> None:
    status, _ = post(api, {"input": "x^2", "intent": "limit", "options": options})
    assert status == 422


def test_warnings_are_returned(api: TestClient) -> None:
    _, data = post(api, {"input": "log(100)"})
    assert [w["code"] for w in data["warnings"]] == ["LOG_BASE_10"]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("1/0", "DIVISION_BY_ZERO"),
        ("sqrt(-1)", "DOMAIN_ERROR"),
        ("2 +", "PARSE_ERROR"),
        ("", "EMPTY_INPUT"),
        ("sin(x) = 0", "UNSUPPORTED_FEATURE"),
        ("10^5000", "LIMIT_EXCEEDED"),
        ("1" * (MAX_INPUT_LENGTH + 1), "INPUT_TOO_LONG"),
        ("__import__('os')", "PARSE_ERROR"),
    ],
)
def test_math_errors_are_answers_not_http_errors(api: TestClient, text: str, code: str) -> None:
    status, data = post(api, {"input": text})
    assert status == 200
    assert data["success"] is False
    assert data["result"] is None
    assert data["error"]["code"] == code
    assert data["error"]["message"]


def test_error_position_points_into_the_input(api: TestClient) -> None:
    _, data = post(api, {"input": "10 + 1/0"})
    assert data["error"]["position"] == 6


def test_intent_mismatch_is_an_answer(api: TestClient) -> None:
    status, data = post(api, {"input": "x + 1", "intent": "arithmetic"})
    assert status == 200
    assert data["error"]["code"] == "INVALID_INPUT_FOR_INTENT"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"input": 42},
        {"input": None},
        {"input": "2+2", "intent": "teleport"},
        {"input": "2+2", "extra": True},
        {"input": "1" * (MAX_REQUEST_INPUT_LENGTH + 1)},
        ["2+2"],
        "2+2",
    ],
)
def test_malformed_requests_are_422(api: TestClient, body: object) -> None:
    status, data = post(api, body)
    assert status == 422
    assert "detail" in data


def test_invalid_json_is_422(api: TestClient) -> None:
    response = api.post(
        "/api/calculate", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_only_post_is_allowed(api: TestClient) -> None:
    assert api.get("/api/calculate").status_code == 405


def test_parallel_requests(api: TestClient) -> None:
    inputs = [f"{n}x + {n} = {3 * n}" for n in range(1, 9)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda text: post(api, {"input": text}), inputs))
    assert [status for status, _ in results] == [200] * 8
    assert [data["result"]["plain"] for _, data in results] == ["x = 2"] * 8


def test_documented_in_openapi(api: TestClient) -> None:
    schema = api.get("/api/openapi.json").json()
    operation = schema["paths"]["/api/calculate"]["post"]
    assert {"200", "422", "500", "503"} <= set(operation["responses"])
