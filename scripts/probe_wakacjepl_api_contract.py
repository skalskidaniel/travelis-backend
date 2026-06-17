#!/usr/bin/env python3
"""Probe Wakacje.pl endpoint contract by mutating request parameters.

This script sends baseline requests plus one-by-one mutations for:
- search endpoint
- calculator variants endpoint
- availability endpoint

Goal: identify which headers/body/query parameters are required for logical success.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.models.cell import MarketCell  # noqa: E402
from core.models.offer import BoardType  # noqa: E402
from core.providers.utils import _month_date_bounds  # noqa: E402
from core.providers.wakacjepl.main import (  # noqa: E402
    AVAILABILITY_URL,
    CALCULATOR_URL,
    SEARCH_URL,
    WakacjePlProvider,
)
from core.providers.wakacjepl.utils import (  # noqa: E402
    _format_wakacje_date,
    _representative_child_birthday,
)


def _next_month_yyyy_mm() -> str:
    today = date.today()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return f"{year}-{month:02d}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return str(value)


def _status_from_payload(payload: dict[str, Any]) -> int | None:
    error_info = payload.get("error")
    status_value: Any = None
    if isinstance(error_info, dict):
        status_value = error_info.get("status")
    if status_value is None:
        status_value = payload.get("status") or payload.get("statusCode")
    if isinstance(status_value, int):
        return status_value
    if isinstance(status_value, str) and status_value.isdigit():
        return int(status_value)
    return None


def _classify_response(endpoint: str, response: httpx.Response) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    parse_error: str | None = None
    try:
        body = response.json()
        parsed = (
            body if isinstance(body, dict) else {"_non_dict_json": _json_safe(body)}
        )
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)

    success_value = parsed.get("success") if parsed else None
    payload_status = _status_from_payload(parsed) if parsed else None

    logical_ok = False
    logical_reason = "unknown"
    if response.status_code != 200:
        logical_reason = "http_status_not_200"
    elif parse_error is not None:
        logical_reason = "json_parse_error"
    elif parsed is None:
        logical_reason = "missing_payload"
    elif success_value is False:
        logical_reason = "success_false"
    elif endpoint == "search":
        data = parsed.get("data")
        if isinstance(data, dict) and isinstance(data.get("offers"), list):
            logical_ok = True
            logical_reason = "offers_list_present"
        else:
            logical_reason = "offers_list_missing"
    elif endpoint == "calculator":
        data = parsed.get("data")
        if isinstance(data, dict) and isinstance(data.get("offers"), list):
            logical_ok = True
            logical_reason = "offers_list_present"
        else:
            logical_reason = "offers_list_missing"
    elif endpoint == "availability":
        data = parsed.get("data")
        if isinstance(data, dict):
            logical_ok = True
            logical_reason = "data_dict_present"
        else:
            logical_reason = "data_dict_missing"

    return {
        "http_status": response.status_code,
        "success": success_value,
        "payload_status": payload_status,
        "logical_ok": logical_ok,
        "logical_reason": logical_reason,
        "payload": _json_safe(parsed),
        "json_parse_error": parse_error,
    }


def _iter_dict_key_paths(
    node: Any, path: tuple[Any, ...] = ()
) -> list[tuple[Any, ...]]:
    paths: list[tuple[Any, ...]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            current = path + (key,)
            paths.append(current)
            paths.extend(_iter_dict_key_paths(value, current))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            paths.extend(_iter_dict_key_paths(item, path + (idx,)))
    return paths


def _parent_and_key(root: Any, path: tuple[Any, ...]) -> tuple[Any, Any]:
    if not path:
        raise ValueError("Path must not be empty")
    node = root
    for step in path[:-1]:
        node = node[step]
    return node, path[-1]


def _mutated_value(original: Any) -> Any:
    if isinstance(original, bool):
        return not original
    if isinstance(original, int):
        return -1 if original >= 0 else 1
    if isinstance(original, float):
        return -1.0 if original >= 0 else 1.0
    if isinstance(original, str):
        return "__INVALID__"
    if original is None:
        return "__INVALID__"
    if isinstance(original, list):
        return ["__INVALID__"]
    if isinstance(original, dict):
        return {"__INVALID__": "__INVALID__"}
    return "__INVALID__"


@dataclass(slots=True)
class EndpointSpec:
    name: str
    method: str
    url: str
    headers: dict[str, str]
    payload: Any
    payload_mode: str  # "json" or "params"


async def _send_request(
    client: httpx.AsyncClient,
    spec: EndpointSpec,
    *,
    headers: dict[str, str],
    payload: Any,
) -> tuple[dict[str, Any], httpx.Response | None]:
    kwargs: dict[str, Any] = {"headers": headers}
    kwargs[spec.payload_mode] = payload
    try:
        if spec.method == "POST":
            response = await client.post(spec.url, **kwargs)
        else:
            response = await client.get(spec.url, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return (
            {
                "http_status": None,
                "success": None,
                "payload_status": None,
                "logical_ok": False,
                "logical_reason": "request_exception",
                "payload": None,
                "json_parse_error": None,
                "request_exception": f"{exc.__class__.__name__}: {exc}",
            },
            None,
        )
    return _classify_response(spec.name, response), response


async def _probe_endpoint(
    client: httpx.AsyncClient,
    spec: EndpointSpec,
    *,
    delay_seconds: float,
) -> dict[str, Any]:
    baseline_result, baseline_response = await _send_request(
        client,
        spec,
        headers=deepcopy(spec.headers),
        payload=deepcopy(spec.payload),
    )

    mutations: list[dict[str, Any]] = []

    for header_name in spec.headers:
        headers_removed = deepcopy(spec.headers)
        headers_removed.pop(header_name, None)
        result_removed, _ = await _send_request(
            client,
            spec,
            headers=headers_removed,
            payload=deepcopy(spec.payload),
        )
        mutations.append(
            {
                "mutation_type": "header_remove",
                "target": header_name,
                "result": result_removed,
            }
        )
        await asyncio.sleep(delay_seconds)

        headers_changed = deepcopy(spec.headers)
        headers_changed[header_name] = "__INVALID__"
        result_changed, _ = await _send_request(
            client,
            spec,
            headers=headers_changed,
            payload=deepcopy(spec.payload),
        )
        mutations.append(
            {
                "mutation_type": "header_invalid_value",
                "target": header_name,
                "result": result_changed,
            }
        )
        await asyncio.sleep(delay_seconds)

    payload_paths = _iter_dict_key_paths(spec.payload)
    for path in payload_paths:
        payload_removed = deepcopy(spec.payload)
        parent, key = _parent_and_key(payload_removed, path)
        if isinstance(parent, dict):
            parent.pop(key, None)
            result_removed, _ = await _send_request(
                client,
                spec,
                headers=deepcopy(spec.headers),
                payload=payload_removed,
            )
            mutations.append(
                {
                    "mutation_type": "payload_remove",
                    "target": ".".join(str(p) for p in path),
                    "result": result_removed,
                }
            )
            await asyncio.sleep(delay_seconds)

        payload_changed = deepcopy(spec.payload)
        parent2, key2 = _parent_and_key(payload_changed, path)
        if isinstance(parent2, dict):
            parent2[key2] = _mutated_value(parent2[key2])
            result_changed, _ = await _send_request(
                client,
                spec,
                headers=deepcopy(spec.headers),
                payload=payload_changed,
            )
            mutations.append(
                {
                    "mutation_type": "payload_invalid_value",
                    "target": ".".join(str(p) for p in path),
                    "result": result_changed,
                }
            )
            await asyncio.sleep(delay_seconds)

    success_count = sum(1 for m in mutations if m["result"]["logical_ok"])
    failure_count = len(mutations) - success_count

    return {
        "endpoint": spec.name,
        "method": spec.method,
        "url": spec.url,
        "baseline": baseline_result,
        "baseline_headers": _json_safe(spec.headers),
        "baseline_payload": _json_safe(spec.payload),
        "baseline_raw_text_preview": (
            baseline_response.text[:600] if baseline_response is not None else None
        ),
        "mutation_count": len(mutations),
        "mutation_success_count": success_count,
        "mutation_failure_count": failure_count,
        "mutations": mutations,
    }


def _build_search_endpoint_spec(
    provider: WakacjePlProvider, cell: MarketCell
) -> EndpointSpec:
    departure_from, departure_to = _month_date_bounds(cell.month)
    country_id = int(provider._country_ids[cell.country])  # noqa: SLF001
    service_id = int(provider._service_values[cell.board.value])  # noqa: SLF001
    payload = provider._build_search_payload(  # noqa: SLF001
        cell=cell,
        page=1,
        country_id=country_id,
        service_id=service_id,
        departure_from=departure_from,
        departure_to=departure_to,
    )
    return EndpointSpec(
        name="search",
        method="POST",
        url=SEARCH_URL,
        headers=provider._search_headers(),  # noqa: SLF001
        payload=payload,
        payload_mode="json",
    )


def _build_calculator_payload(
    search_item: dict[str, Any], adults: int, children: int
) -> dict[str, Any]:
    child_birthday = _representative_child_birthday()
    children_birthdays = [child_birthday] * children

    service_id = int(search_item.get("service", 1))
    duration = int(search_item.get("durationNights", 7))
    departure_date = str(search_item["departureDate"])
    transport_id = int(search_item.get("departureType", 1))
    departure_iata = str(search_item["departurePlaceCode"])
    hotel_id = int(search_item["hotelId"])
    tour_id = int(search_item["tourOperator"])
    tour_op_code = search_item.get("tourOpCode")

    from core.providers.resources import wakacjepl_filters

    departure_places = wakacjepl_filters["departurePlaces"]
    departure_city_id = int(departure_places[departure_iata]["id"])

    payload: dict[str, Any] = {
        "adults": adults,
        "kids": children,
        "infants": 0,
        "kidsAges": children_birthdays,
        "serviceId": service_id,
        "duration": duration,
        "departureDate": _format_wakacje_date(
            datetime.fromisoformat(departure_date).date()
        ),
        "transportId": transport_id,
        "departureCityId": departure_city_id,
        "departureCityCode": departure_iata,
        "hotelId": hotel_id,
        "tourId": tour_id,
        "cruiseId": 0,
        "roundTripId": 0,
        "isAlternativeRoom": False,
        "isOffer77": False,
    }
    if tour_op_code:
        payload["tourOp"] = str(tour_op_code)
    return payload


def _build_availability_spec(
    search_item: dict[str, Any],
    *,
    offer_hash: str,
    provider_code: str,
    adults: int,
    children: int,
) -> EndpointSpec:
    place = search_item["place"]
    custom_headers = json.dumps(
        {
            "Page-Source": "PO",
            "Tour-Operator-Code": provider_code,
            "Tour-Operator-Id": str(search_item["tourOperator"]),
            "Object-Id": str(search_item["hotelId"]),
        }
    )
    headers = {
        "accept": "application/json",
        "referer": f"https://www.wakacje.pl/wczasy/{place['country']['slug']}/{place['region']['slug']}/{place['city']['slug']}/{search_item['urlName']}-{search_item['offerId']}.html",
        "customHeaders": custom_headers,
    }

    params: dict[str, Any] = {
        "providerCode": provider_code,
        "offerHash": offer_hash,
        "offerType": "tour",
        "includeTfgService": "true",
        "isAlternativeRoom": "false",
        "cityId": int(place["city"]["id"]),
        "countryId": int(place["country"]["id"]),
        "regionId": int(place["region"]["id"]),
    }

    for i in range(adults):
        params[f"participantsObject[participants][{i}][birthDate]"] = "1988-01-01"
        params[f"participantsObject[participants][{i}][type]"] = "adult"
        params[f"participantsObject[participants][{i}][userAllocateId]"] = i + 1

    idx = adults
    child_birthday_fmt = _representative_child_birthday()
    child_iso = (
        f"{child_birthday_fmt[:4]}-{child_birthday_fmt[4:6]}-{child_birthday_fmt[6:]}"
    )
    for _ in range(children):
        params[f"participantsObject[participants][{idx}][birthDate]"] = child_iso
        params[f"participantsObject[participants][{idx}][type]"] = "child"
        params[f"participantsObject[participants][{idx}][userAllocateId]"] = idx + 1
        idx += 1

    return EndpointSpec(
        name="availability",
        method="GET",
        url=AVAILABILITY_URL,
        headers=headers,
        payload=params,
        payload_mode="params",
    )


async def run_probe(args: argparse.Namespace) -> Path:
    timeout = httpx.Timeout(args.timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        provider = WakacjePlProvider(client=client)
        cell = MarketCell(
            cell_id="1111111111111111",
            country=args.country,
            month=args.month,
            min_stars=args.min_stars,
            board=BoardType(args.board),
            adults=args.adults,
            children=args.children,
            activation_count=1,
        )

        search_spec = _build_search_endpoint_spec(provider, cell)
        print("Probing endpoint: search")
        search_report = await _probe_endpoint(
            client, search_spec, delay_seconds=args.delay_seconds
        )

        baseline_payload = search_report["baseline"]["payload"] or {}
        offers = (
            baseline_payload.get("data", {}).get("offers", [])
            if isinstance(baseline_payload, dict)
            else []
        )
        if not offers:
            raise RuntimeError(
                "Search baseline returned no offers, cannot probe calculator/availability."
            )

        search_item = offers[0]
        external_offer_id = str(search_item["offerId"])

        calculator_spec = EndpointSpec(
            name="calculator",
            method="POST",
            url=CALCULATOR_URL.format(offer_id=external_offer_id),
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "origin": "https://www.wakacje.pl",
                "referer": f"https://www.wakacje.pl/wczasy/{search_item['place']['country']['slug']}/{search_item['place']['region']['slug']}/{search_item['place']['city']['slug']}/{search_item['urlName']}-{search_item['offerId']}.html",
            },
            payload=_build_calculator_payload(search_item, args.adults, args.children),
            payload_mode="json",
        )
        print("Probing endpoint: calculator")
        calculator_report = await _probe_endpoint(
            client, calculator_spec, delay_seconds=args.delay_seconds
        )

        calc_payload = calculator_report["baseline"]["payload"] or {}
        variants = (
            calc_payload.get("data", {}).get("offers", [])
            if isinstance(calc_payload, dict)
            else []
        )
        if not variants:
            raise RuntimeError(
                "Calculator baseline returned no variants, cannot probe availability."
            )
        variant = variants[0]
        offer_hash = str(variant["id"])
        provider_code = str(
            variant.get("providerCode") or search_item.get("tourOpCode") or "WAK"
        )

        availability_spec = _build_availability_spec(
            search_item,
            offer_hash=offer_hash,
            provider_code=provider_code,
            adults=args.adults,
            children=args.children,
        )
        print("Probing endpoint: availability")
        availability_report = await _probe_endpoint(
            client, availability_spec, delay_seconds=args.delay_seconds
        )

    summary = {
        "search": {
            "baseline_logical_ok": search_report["baseline"]["logical_ok"],
            "mutation_count": search_report["mutation_count"],
            "mutation_failure_count": search_report["mutation_failure_count"],
        },
        "calculator": {
            "baseline_logical_ok": calculator_report["baseline"]["logical_ok"],
            "mutation_count": calculator_report["mutation_count"],
            "mutation_failure_count": calculator_report["mutation_failure_count"],
        },
        "availability": {
            "baseline_logical_ok": availability_report["baseline"]["logical_ok"],
            "mutation_count": availability_report["mutation_count"],
            "mutation_failure_count": availability_report["mutation_failure_count"],
        },
    }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "country": args.country,
            "month": args.month,
            "min_stars": args.min_stars,
            "board": args.board,
            "adults": args.adults,
            "children": args.children,
            "timeout_seconds": args.timeout_seconds,
            "delay_seconds": args.delay_seconds,
        },
        "summary": summary,
        "reports": [search_report, calculator_report, availability_report],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return args.output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Wakacje.pl contract with one-by-one request mutations."
    )
    parser.add_argument(
        "--country", default="GR", help="ISO country code for search cell."
    )
    parser.add_argument(
        "--month",
        default=_next_month_yyyy_mm(),
        help="Search month in YYYY-MM format (default: next month).",
    )
    parser.add_argument("--min-stars", type=int, default=4)
    parser.add_argument(
        "--board",
        default="all-inclusive",
        choices=[b.value for b in BoardType],
        help="Board type used for baseline search payload.",
    )
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.15,
        help="Sleep between mutation requests to reduce accidental rate limiting.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scripts" / "artifacts" / "wakacjepl_contract_probe.json",
        help="Output JSON report path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = asyncio.run(run_probe(args))
    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
