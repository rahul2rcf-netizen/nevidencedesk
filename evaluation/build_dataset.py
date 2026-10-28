"""Build the versioned synthetic evaluation set deterministically."""
import json
from pathlib import Path

facts = [
 ("When does the community center open on weekdays?", "8:00 AM", "The community center opens at 8:00 AM on weekdays."),
 ("What time does the center close Monday through Friday?", "9:00 PM", "The building closes at 9:00 PM Monday through Friday."),
 ("What are weekend opening hours?", "10:00 AM to 6:00 PM", "Weekend hours are 10:00 AM to 6:00 PM."),
 ("Where must visitors register?", "front desk", "Visitors must sign in at the front desk."),
 ("What should staff wear visibly inside?", "Staff badges", "Staff badges must be visible inside the building."),
 ("Which entrance has a ramp?", "west entrance", "The west entrance is accessible by ramp."),
 ("How many spaces are in the public parking lot?", "42 spaces", "The public parking lot has 42 spaces."),
 ("Where are bicycle racks located?", "beside the north entrance", "Bicycle racks are located beside the north entrance."),
 ("Which floor has reception?", "ground floor", "The reception desk is on the ground floor."),
 ("How many public floors does the building have?", "three", "The building has three public floors."),
 ("How far in advance can a meeting room be booked?", "60 days", "Meeting rooms may be reserved up to 60 days in advance."),
 ("What is the maximum length for a standard room booking?", "two hours", "A standard room reservation lasts no more than two hours."),
 ("Do community groups pay for room use?", "no charge", "Community groups receive room use at no charge."),
 ("When should a reservation be cancelled?", "at least 24 hours before", "Reservations must be cancelled at least 24 hours before the start time."),
 ("What is the capacity of the largest meeting room?", "30 people", "The largest meeting room holds 30 people."),
 ("How many people fit in the small study room?", "4 people", "The small study room holds 4 people."),
 ("Where do people collect room keys?", "reception", "Room keys are collected from reception."),
 ("In which room is food permitted?", "conference room", "Food is allowed only in the conference room."),
 ("Where is the projector kept?", "meeting room B", "The projector is stored in meeting room B."),
 ("When does a large event need staff approval?", "more than 20 attendees", "Events with more than 20 attendees require staff approval."),
 ("When does program registration begin each month?", "first day", "Program registration opens on the first day of each month."),
 ("Who gets priority for a full class?", "Residents", "Residents receive priority when a class is full."),
 ("How many classes may a participant join per season?", "three", "A participant may join up to three classes per season."),
 ("How many seasonal sessions are held each year?", "six", "The center offers six seasonal sessions each year."),
 ("How are class cancellations communicated?", "email", "Class cancellations are sent by email."),
 ("Who must accompany a participant younger than 12?", "an adult", "Participants under age 12 must attend with an adult."),
 ("In what season are swimming lessons offered?", "summer", "The swimming lesson program is offered in summer."),
 ("Which day is the art studio closed?", "Mondays", "The art studio is closed on Mondays."),
 ("What happens when a class reaches capacity?", "A waitlist", "A waitlist is used when a class reaches capacity."),
 ("How long after registration can a refund be requested?", "seven days", "Refund requests must be submitted within seven days of registration."),
 ("How many items can a member borrow from the lending library?", "two items", "The lending library allows two items per member."),
 ("What is the loan period for library items?", "14 days", "Items may be borrowed for 14 days."),
 ("How much is the daily late return fee?", "one dollar per day", "A late return fee is one dollar per day."),
 ("How many plots are in the community garden?", "18 plots", "The community garden has 18 plots."),
 ("When are garden plot applications due?", "March 1", "Garden plot applications are due by March 1."),
 ("How many workstations are in the computer lab?", "12 workstations", "The computer lab contains 12 workstations."),
 ("What is the public computer session limit?", "one hour", "Public computer sessions are limited to one hour."),
 ("What is the cost per black-and-white printed page?", "ten cents", "Printing costs ten cents per black-and-white page."),
 ("Is public Wi-Fi free?", "free", "The center provides free public Wi-Fi."),
 ("How long is lost property held?", "30 days", "Lost property is held for 30 days."),
]
unknown = ["What is the center's annual operating budget?", "How many employees work at the center?", "What brand are the computers?", "Who designed the building?", "What is the director's home address?", "How many visitors came last year?", "What is the price of a garden plot?", "Which company supplies the Wi-Fi?", "What is the center's social media password?", "How many square meters is the building?"]
items = [{"id": f"v1-a{i:02d}", "question": q, "answerable": True, "expected_answer": a, "supporting_document_id": "northstar-demo", "supporting_pages": [1], "evidence": evidence} for i, (q, a, evidence) in enumerate(facts, 1)]
items += [{"id": f"v1-u{i:02d}", "question": q, "answerable": False, "expected_answer": "", "supporting_document_id": None, "supporting_pages": [], "evidence": ""} for i, q in enumerate(unknown, 1)]
path = Path(__file__).parent / "dataset" / "v1.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({"version": "1.0.0", "label": "SYNTHETIC DEMO DATA — fictional community center handbook", "questions": items}, indent=2), encoding="utf-8")
print(f"Wrote {len(items)} cases ({len(facts)} answerable, {len(unknown)} unanswerable) to {path}")
