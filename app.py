"""Show timetable slots where every selected staff member is available."""

from __future__ import annotations

import csv
import hmac
import io
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path

import streamlit as st


DEFAULT_CSV = Path("staff_timetable.csv")
DAYS = ("MON", "TUE", "WED", "THU", "FRI")
TIMES = tuple(f"{hour:02}:15" for hour in range(9, 17))
REQUIRED_COLUMNS = {"Staff Name", "Day", "Time", "Duration"}


@st.cache_data
def load_timetable(contents: bytes) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(contents.decode("utf-8-sig"))))
    columns = set(rows[0]) if rows else set()
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}")
    return rows


def normalise_day(value: str) -> str:
    return value.strip().upper()[:3]


def require_password() -> None:
    password = st.secrets.get("password", "")
    if not isinstance(password, str) or not password:
        st.error(
            "Set a non-empty `password` in `.streamlit/secrets.toml` before "
            "starting the app."
        )
        st.stop()

    if st.session_state.get("authenticated"):
        return

    with st.form("password-form"):
        entered_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("View timetable")

    if submitted:
        if hmac.compare_digest(entered_password, password):
            st.session_state.authenticated = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


def occupied_slots(rows: list[dict[str, str]], staff: set[str]) -> dict[tuple[str, str], set[str]]:
    occupied: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in rows:
        name = row["Staff Name"].strip()
        day = normalise_day(row["Day"])
        start = row["Time"].strip()
        if name not in staff or day not in DAYS or start not in TIMES:
            continue

        duration = float(row["Duration"] or 1)
        slot_count = max(1, ceil(duration))
        start_time = datetime.strptime(start, "%H:%M")
        for offset in range(slot_count):
            time = (start_time + timedelta(hours=offset)).strftime("%H:%M")
            if time in TIMES:
                occupied[(day, time)].add(name)

    return occupied


def main() -> None:
    st.set_page_config(page_title="Staff availability", layout="wide")
    st.title("Staff availability")
    st.caption("Find timetable slots when every selected staff member is free.")
    require_password()

    if not DEFAULT_CSV.is_file():
        st.info(
            "Create `staff_timetable.csv` in this directory with "
            "`extract_timetables.py` before starting the app."
        )
        st.stop()
    contents = DEFAULT_CSV.read_bytes()

    try:
        rows = load_timetable(contents)
    except ValueError as error:
        st.error(str(error))
        st.stop()

    staff_names = sorted({row["Staff Name"].strip() for row in rows if row["Staff Name"].strip()})
    selected_staff = st.multiselect("Staff members", staff_names)
    st.caption(f"Using {DEFAULT_CSV}")

    if not selected_staff:
        st.info("Select one or more staff members to view common free slots.")
        st.stop()

    occupied = occupied_slots(rows, set(selected_staff))
    free_slots = [
        {"Day": day, "Time": time}
        for day in DAYS
        for time in TIMES
        if not occupied[(day, time)]
    ]
    availability_grid = [
        {
            "Time": time,
            **{
                day: "Free" if not occupied[(day, time)] else "Busy"
                for day in DAYS
            },
        }
        for time in TIMES
    ]

    st.metric("Common free slots", f"{len(free_slots)} of {len(DAYS) * len(TIMES)}")
    st.subheader("Weekly availability")
    st.dataframe(availability_grid, hide_index=True, use_container_width=True)
    st.subheader("Common free slots")
    st.dataframe(free_slots, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
