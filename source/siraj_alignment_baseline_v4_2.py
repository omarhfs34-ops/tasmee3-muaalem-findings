import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple
import Levenshtein
import numpy as np
import pandas as pd


@dataclass
class RawOp:
    op: str  # 'equal', 'replace', 'delete', 'insert'
    ref_range: Tuple[int, int]
    pred_range: Tuple[int, int]
    ref_groups: List[str]  # سلاسل نصية تمثل مجموعات فونيمية وليست أحرفاً ذرية
    pred_groups: List[str]


@dataclass
class BaselineErrorRecord:
    surah: int
    ayah: int
    affected_word_indices: List[int]
    word_index: Optional[
        int
    ]  # للتوافق الخلفي عند وجود كلمة واحدة فقط متأثرة
    display_type: str  # 'replace', 'delete', 'insert'
    derived_substitution: bool
    derived_substitution_reason: Optional[str]
    raw_operations: List[dict]
    ref_groups: List[str]
    pred_groups: List[str]
    word_uthmani_span: Optional[
        Tuple[int, int]
    ] = None
    affected_word_uthmani_spans: List[Tuple[int, int]] = field(
        default_factory=list
    )
    ref_group_anchor: Optional[Tuple[int, int]] = None
    ref_group_before: Optional[int] = None
    ref_group_after: Optional[int] = None
    anchor_kind: str = "inside_word"
    word_span_is_exact: bool = True
    character_span_is_exact: bool = False
    confidence: Optional[float] = None
    confidence_source: str = "not_computed"


class VerifiedQuranBridge:
    def __init__(
        self,
        ph_index_path: str = "ph_index.npy",
        expected_hash: Optional[str] = None,
    ):
        path = Path(ph_index_path)
        if not path.exists():
            raise FileNotFoundError(f"لم يتم العثور على الفهرس: {ph_index_path}")

        raw_bytes = path.read_bytes()
        self.computed_hash = hashlib.sha256(raw_bytes).hexdigest()[:12]

        if expected_hash and self.computed_hash != expected_hash:
            raise ValueError(
                f"تعارض في الـ Hash! المتوقع: {expected_hash}، المحسوب: {self.computed_hash}"
            )

        raw_data = np.load(ph_index_path, allow_pickle=False)

        if raw_data.ndim != 2 or raw_data.shape[1] != 7:
            raise ValueError(
                f"شكل الفهرس غير صحيح! المتوقع (N, 7)، الحالي: {raw_data.shape}"
            )

        self.df = pd.DataFrame(
            raw_data,
            columns=[
                "surah",
                "ayah",
                "word",
                "txt_start",
                "txt_end",
                "ph_start",
                "ph_end",
            ],
        )

        if not np.all(self.df["txt_start"] <= self.df["txt_end"]):
            raise ValueError("خطأ في النطاق النصي في الفهرس: txt_start > txt_end")
        if not np.all(self.df["ph_start"] <= self.df["ph_end"]):
            raise ValueError(
                "خطأ في النطاق الصوتي في الفهرس: ph_start > ph_end"
            )

    def get_ayah_group_table(self, surah: int, ayah: int) -> pd.DataFrame:
        rows = (
            self.df[(self.df["surah"] == surah) & (self.df["ayah"] == ayah)]
            .sort_index()
            .copy()
        )
        if rows.empty:
            raise ValueError(
                f"لا توجد بيانات فهرس خاصة بالسورة {surah} والآية {ayah}"
            )
        rows["group_idx"] = range(len(rows))
        return rows

    def get_ayah_word_table(self, surah: int, ayah: int) -> pd.DataFrame:
        rows = self.get_ayah_group_table(surah, ayah)
        word_table = (
            rows.groupby("word", sort=True)
            .agg(
                group_start=("group_idx", "min"),
                group_end=("group_idx", "max"),
                txt_start=("txt_start", "min"),
                txt_end=("txt_end", "max"),
            )
            .reset_index()
        )
        word_table["group_end"] = word_table["group_end"] + 1
        return word_table


class SirajAlignmentBaselineV4:
    def __init__(self, bridge: VerifiedQuranBridge):
        self.bridge = bridge

    @staticmethod
    def compute_reference_hash(ref_groups: List[str]) -> str:
        payload = "\x1f".join(
            f"{len(g)}:{g}" for g in ref_groups
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]

    def locate_insertion(
        self, word_table: pd.DataFrame, group_idx: int
    ) -> Tuple[List[int], str]:
        before = word_table[word_table["group_end"] == group_idx]
        after = word_table[word_table["group_start"] == group_idx]

        if not before.empty and not after.empty:
            words = [int(before.iloc[0]["word"]), int(after.iloc[0]["word"])]
            return words, "word_boundary"

        inside = word_table[
            (word_table["group_start"] <= group_idx)
            & (group_idx < word_table["group_end"])
        ]
        if len(inside) == 1:
            return [int(inside.iloc[0]["word"])], "inside_word"

        if not before.empty:
            return [int(before.iloc[0]["word"])], "after_word"
        if not after.empty:
            return [int(after.iloc[0]["word"])], "before_word"

        return [], "outside_ayah"

    def align_ayah_global_baseline(
        self,
        surah: int,
        ayah: int,
        ref_ph_groups: List[Tuple[str, ...]],
        pred_ph_groups: List[Tuple[str, ...]],
        expected_ref_hash: Optional[str] = None,
    ) -> List[BaselineErrorRecord]:

        word_table = self.bridge.get_ayah_word_table(surah, ayah)
        group_table = self.bridge.get_ayah_group_table(surah, ayah)

        if len(ref_ph_groups) != len(group_table):
            raise ValueError(
                f"عدم تطابق عدد مجموعات المرجع ({len(ref_ph_groups)}) مع الفهرس ({len(group_table)}) للآية {surah}:{ayah}"
            )

        ref_strings = ["".join(g) for g in ref_ph_groups]
        pred_strings = ["".join(g) for g in pred_ph_groups]

        if expected_ref_hash:
            current_ref_hash = self.compute_reference_hash(ref_strings)
            if current_ref_hash != expected_ref_hash:
                raise ValueError(
                    f"تعارض محتوى المرجع الصوتي! المتوقع: {expected_ref_hash}، الحالي: {current_ref_hash}"
                )

        opcodes = Levenshtein.opcodes(ref_strings, pred_strings)
        raw_records: List[BaselineErrorRecord] = []

        for op, r1, r2, p1, p2 in opcodes:
            if op == "equal":
                continue

            ref_sub = list(ref_strings[r1:r2])
            pred_sub = list(pred_strings[p1:p2])

            raw_op = RawOp(
                op=op,
                ref_range=(int(r1), int(r2)),
                pred_range=(int(p1), int(p2)),
                ref_groups=ref_sub,
                pred_groups=pred_sub,
            )

            affected_words: List[int] = []
            anchor_kind = "inside_word"
            ref_group_before: Optional[int] = None
            ref_group_after: Optional[int] = None

            if op == "insert" and r1 == r2:
                affected_words, anchor_kind = self.locate_insertion(
                    word_table, r1
                )
                ref_group_before = int(r1 - 1) if r1 > 0 else None
                ref_group_after = int(r1) if r1 < len(ref_strings) else None
            else:
                matched = word_table[
                    (word_table["group_start"] < r2)
                    & (word_table["group_end"] > r1)
                ]
                affected_words = [int(w) for w in matched["word"].tolist()]
                anchor_kind = (
                    "multi_word" if len(affected_words) > 1 else "inside_word"
                )

            affected_spans: List[Tuple[int, int]] = []
            for w_idx in affected_words:
                w_info = word_table[word_table["word"] == w_idx]
                if not w_info.empty:
                    affected_spans.append(
                        (
                            int(w_info.iloc[0]["txt_start"]),
                            int(w_info.iloc[0]["txt_end"]),
                        )
                    )

            txt_span = None
            primary_word = None
            if len(affected_words) == 1 and anchor_kind != "word_boundary":
                primary_word = affected_words[0]
                txt_span = affected_spans[0] if affected_spans else None

            raw_records.append(
                BaselineErrorRecord(
                    surah=surah,
                    ayah=ayah,
                    affected_word_indices=affected_words,
                    word_index=primary_word,
                    display_type=op,
                    derived_substitution=False,
                    derived_substitution_reason=None,
                    raw_operations=[asdict(raw_op)],
                    ref_groups=ref_sub,
                    pred_groups=pred_sub,
                    word_uthmani_span=txt_span,
                    affected_word_uthmani_spans=affected_spans,
                    ref_group_anchor=(int(r1), int(r2)),
                    ref_group_before=ref_group_before,
                    ref_group_after=ref_group_after,
                    anchor_kind=anchor_kind,
                    word_span_is_exact=True,
                    character_span_is_exact=False,
                    confidence=None,
                )
            )

        return self._apply_strict_post_pass(raw_records)

    def _apply_strict_post_pass(
        self, records: List[BaselineErrorRecord]
    ) -> List[BaselineErrorRecord]:
        if len(records) < 2:
            return records

        processed: List[BaselineErrorRecord] = []
        i = 0
        n = len(records)

        while i < n:
            curr = records[i]

            if i < n - 1:
                nxt = records[i + 1]

                is_del_ins = {curr.display_type, nxt.display_type} == {
                    "delete",
                    "insert",
                }
                is_single_word = len(curr.affected_word_indices) == 1
                same_words = (
                    curr.affected_word_indices == nxt.affected_word_indices
                )

                if (
                    is_del_ins
                    and is_single_word
                    and same_words
                    and curr.affected_word_indices
                ):
                    curr_op = curr.raw_operations[-1]
                    nxt_op = nxt.raw_operations[0]

                    ref_adjacent = (
                        curr_op["ref_range"][1] == nxt_op["ref_range"][0]
                        or nxt_op["ref_range"][1] == curr_op["ref_range"][0]
                    )
                    pred_adjacent = (
                        curr_op["pred_range"][1] == nxt_op["pred_range"][0]
                        or nxt_op["pred_range"][1] == curr_op["pred_range"][0]
                    )

                    if ref_adjacent and pred_adjacent:
                        merged_ref = curr.ref_groups + nxt.ref_groups
                        merged_pred = curr.pred_groups + nxt.pred_groups
                        merged_raw_ops = (
                            curr.raw_operations + nxt.raw_operations
                        )

                        ref_start = min(
                            curr_op["ref_range"][0], nxt_op["ref_range"][0]
                        )
                        ref_end = max(
                            curr_op["ref_range"][1], nxt_op["ref_range"][1]
                        )

                        processed.append(
                            BaselineErrorRecord(
                                surah=curr.surah,
                                ayah=curr.ayah,
                                affected_word_indices=curr.affected_word_indices,
                                word_index=curr.word_index,
                                display_type="replace",
                                derived_substitution=True,
                                derived_substitution_reason="adjacent_delete_insert_within_single_word",
                                raw_operations=merged_raw_ops,
                                ref_groups=merged_ref,
                                pred_groups=merged_pred,
                                word_uthmani_span=curr.word_uthmani_span,
                                affected_word_uthmani_spans=curr.affected_word_uthmani_spans,
                                ref_group_anchor=(ref_start, ref_end),
                                anchor_kind=curr.anchor_kind,
                                word_span_is_exact=curr.word_span_is_exact,
                                character_span_is_exact=False,
                                confidence=None,
                            )
                        )
                        i += 2
                        continue

            processed.append(curr)
            i += 1

        return processed
