#import "para-lipics/lib.typ": *

#show: para-lipics.with(
   title: [ssalsa: Incrementalized Computation for Python],
   authors: (
      (
         name: "falfia",
         email: "nicola@ucsc.edu",
         website: "https://falfia.fi",
         orcid: "0009-0000-6248-2728",
         affiliations: "University of California, Santa Cruz",
      ),
   ),
   hide-lipics: true,
   hide-doi: true,
   keywords: "Incremental Computation, Lazy Evaluation, Python, Calc Chain",
   category: "Technical Report, Literature Review, Procrastination Research",
   event-short-title: "CSE 290Q",
   abstract: [
      Total memoization avoids as much computation as possible with a huge storage and hashing cost. In most cases we can do better or something.
      Python is missing a good incremental compilation library. I aim to fix this by ripping off salsa #cite(<salsa-rs>) wholesale and writing a tiny literature review on the subject.
   ],
)

#place(top + right, dy: -5em, text(fill: gray)[#datetime.today().display()])

= History
// Brief history: 300 words

- excel
- adapton
- glimmer
- rustc's query system

= Design Considerations

- Lazy, Eager
- Event framework
- Automatic detection of dependencies
   - Proof that if there are dependencies out of date, we will detect them even when there's non-determinism
   - Considerations that we don't know ahead of time what the dependencies are going to be.
   - But I have a type system that does that!


== Total Caching

== Salsa: Single Cell Caching

Turns out that trying to hash all the values takes a lotta time so we don't do it anymore.

#figure(caption: "Syntax of Salsa")[
   \
   #grid(
      align: (right, center, left, right),
      row-gutter: 1em,
      column-gutter: (5pt, 5pt, 2em),
      columns: 4,
      $v$, [], [], "Value",
      $r$, $:$, $sans("int")$, "Revision",
      $m$, $≔$, $⟨v, sans("created_at:") r, sans("verified_at:") r⟩$, "Memo",
      $𝕜$, $≔$, $[overline(x ↦ v)]$, "Key",
      $Q$, $:$, $𝕜 → m$, "Query"
   )
]


== Online Resources

Motivate the case of online resources where the values may have been changed. Perhaps there's some known staleness idea.

= Future Research
// How this relates to, say, JavaScript's React or Solid.js

- How this relates to 

#align(bottom)[
   #bibliography("bibliography.bib")
]
