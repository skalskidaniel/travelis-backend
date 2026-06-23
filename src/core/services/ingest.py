import hashlib
import re
import unicodedata

from core.models.common import ProviderName
from core.models.offer import (
    Offer,
    OfferMetadata,
    OfferSource,
    RawOffer,
)


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing, stripping accents/diacritics,
    replacing special characters, retaining only alphanumeric characters and
    spaces, and collapsing multiple spaces.
    """
    text = text.lower()
    text = text.replace("ł", "l").replace("ß", "ss")
    nfkd_form = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_hotel(hotel_name: str, country: str, region: str) -> str:
    """Standardize the hotel identity by combining normalized hotel name, country, and region."""
    return (
        f"{normalize_text(hotel_name)}:"
        f"{normalize_text(country)}:"
        f"{normalize_text(region)}"
    )


def compute_offer_id(offer: RawOffer) -> str:
    """Compute the 32-character SHA-256 fingerprint prefix (offer_id) based on trip semantics."""
    parts = offer.location.split("/")
    country = parts[0]
    region = parts[1]

    norm_hotel = normalize_hotel(offer.hotel_name, country, region)
    norm_room = normalize_text(offer.room_type)

    components = [
        norm_hotel,
        offer.departure_date.isoformat(),
        offer.return_date.isoformat(),
        offer.departure_airport.upper().strip(),
        offer.board.value.lower().strip(),
        norm_room,
        str(offer.adults),
        str(offer.children),
    ]

    raw_key = ":".join(components)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


def ingest_raw_offers(offers: list[RawOffer]) -> list[RawOffer]:
    """Process a batch of raw scraped offers, grouping and collapsing variants
    with the same semantic fingerprint (lowest price total wins).
    """
    if not offers:
        return []

    groups: dict[str, list[RawOffer]] = {}
    for offer in offers:
        oid = compute_offer_id(offer)
        groups.setdefault(oid, []).append(offer)

    collapsed_offers: list[RawOffer] = []
    for group in groups.values():
        winner = min(group, key=lambda o: o.price_total)

        sources: list[OfferSource] = []
        for o in group:
            tour_op = None
            if o.provider == ProviderName.WAKACJE_PL and o.metadata.wakacje_pl:
                tour_op = o.metadata.wakacje_pl.tour_op_code

            sources.append(
                OfferSource(
                    provider=o.provider,
                    external_offer_id=o.external_offer_id,
                    price_total=o.price_total,
                    tour_operator=tour_op,
                )
            )

        deduped_sources: dict[tuple[ProviderName, str], OfferSource] = {}
        for src in sources:
            deduped_sources[(src.provider, src.external_offer_id)] = src

        winner_metadata_dict = winner.metadata.model_dump()
        winner_metadata_dict["sources"] = list(deduped_sources.values())

        has_wakacje = any(o.provider == ProviderName.WAKACJE_PL for o in group)
        has_tui = any(o.provider == ProviderName.TUI for o in group)

        if has_wakacje and not winner_metadata_dict.get("wakacje_pl"):
            for o in group:
                if o.metadata.wakacje_pl:
                    winner_metadata_dict["wakacje_pl"] = (
                        o.metadata.wakacje_pl.model_dump()
                    )
                    break

        if has_tui and not winner_metadata_dict.get("tui"):
            for o in group:
                if o.metadata.tui:
                    winner_metadata_dict["tui"] = o.metadata.tui.model_dump()
                    break

        winner_dict = winner.model_dump()
        winner_dict["metadata"] = OfferMetadata(**winner_metadata_dict)
        collapsed_offers.append(RawOffer(**winner_dict))

    return collapsed_offers


def merge_sources(
    existing_sources: list[OfferSource],
    new_sources: list[OfferSource],
    new_provider: ProviderName,
) -> list[OfferSource]:
    """Merge existing and new sources.
    Prunes existing sources from the new scraped provider that are no longer present
    in the new scrape results.
    """
    new_active_ids = {
        src.external_offer_id for src in new_sources if src.provider == new_provider
    }

    filtered_existing = [
        src
        for src in existing_sources
        if src.provider != new_provider or src.external_offer_id in new_active_ids
    ]

    merged: dict[tuple[ProviderName, str], OfferSource] = {}
    for src in filtered_existing:
        merged[(src.provider, src.external_offer_id)] = src
    for src in new_sources:
        merged[(src.provider, src.external_offer_id)] = src

    return list(merged.values())


def merge_existing_and_new_offer(existing: Offer, new: Offer) -> Offer:
    """Merge an existing persisted offer with a newly scraped and scored offer.
    Selects the lowest-priced variant from the merged sources list as the winner,
    updates top-level fields, merges provider metadata blocks, and refreshes the timestamps.
    """
    existing_srcs = existing.metadata.sources
    if not existing_srcs:
        tour_op = None
        if (
            existing.provider == ProviderName.WAKACJE_PL
            and existing.metadata.wakacje_pl
        ):
            tour_op = existing.metadata.wakacje_pl.tour_op_code
        existing_srcs = [
            OfferSource(
                provider=existing.provider,
                external_offer_id=existing.external_offer_id,
                price_total=existing.price_total,
                tour_operator=tour_op,
            )
        ]

    new_srcs = new.metadata.sources
    if not new_srcs:
        tour_op = None
        if new.provider == ProviderName.WAKACJE_PL and new.metadata.wakacje_pl:
            tour_op = new.metadata.wakacje_pl.tour_op_code
        new_srcs = [
            OfferSource(
                provider=new.provider,
                external_offer_id=new.external_offer_id,
                price_total=new.price_total,
                tour_operator=tour_op,
            )
        ]

    merged_sources_list = merge_sources(
        existing_sources=existing_srcs,
        new_sources=new_srcs,
        new_provider=new.provider,
    )

    cheapest_source = min(merged_sources_list, key=lambda s: s.price_total)

    if cheapest_source.provider == new.provider:
        winner_offer = new
    elif cheapest_source.provider == existing.provider:
        winner_offer = existing
    else:
        winner_offer = new

    has_wakacje = any(
        src.provider == ProviderName.WAKACJE_PL for src in merged_sources_list
    )
    has_tui = any(src.provider == ProviderName.TUI for src in merged_sources_list)

    merged_wakacje_pl = None
    if has_wakacje:
        merged_wakacje_pl = new.metadata.wakacje_pl or existing.metadata.wakacje_pl

    merged_tui = None
    if has_tui:
        merged_tui = new.metadata.tui or existing.metadata.tui

    price_z_score = winner_offer.metadata.price_z_score

    merged_metadata = OfferMetadata(
        price_z_score=price_z_score,
        sources=merged_sources_list,
        wakacje_pl=merged_wakacje_pl,
        tui=merged_tui,
    )

    merged_offer_dict = winner_offer.model_dump()
    merged_offer_dict["metadata"] = merged_metadata
    merged_offer_dict["scraped_at"] = new.scraped_at
    merged_offer_dict["updated_at"] = new.updated_at

    return Offer(**merged_offer_dict)
