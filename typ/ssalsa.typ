#import "para-lipics/lib.typ": *

#show: para-lipics.with(
   title: [ssalsa: Incrementalized Computation for Python],
   authors: (),
   hide-lipics: true,
   hide-doi: true,
   keywords: "Incremental Computation, Calc Chain, Lazy Evaluation, Python",
   category: "Literature Review, Technical Report",
   event-short-title: "CSE 290Q",
   abstract: [
      Python is missing a good incremental compilation library. I aim to fix this by ripping off salsa #cite(<salsa-rs>) wholesale.
   ],
)

#place(top + right, dy: -5em, text(fill: gray)[#datetime.today().display()])

= History
// Brief history: 300 words

- adapton
- glimmer
- rustc's query system

= Design Considerations

- Lazy, Eager


== Total Caching

== Salsa: Single Cell Caching

A query is a $sans("Tuple")⟨v⟩ → ⟨v, sans("created_at:") r, sans("verified_at:") r⟩$



== Online Resources

Motivate the case of online resources where the values may have been changed. Perhaps there's some known staleness idea.

= Future Research
// How this relates to, say, JavaScript's React or Solid.js

- How this relates to 

#align(bottom)[
   #bibliography("bibliography.bib")
]
