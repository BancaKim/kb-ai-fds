const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, TableOfContents
} = require("docx");

// ── Colors ──
const C = {
  primary: "1B3A5C",   // 진한 남색
  accent: "2E75B6",    // 파란색
  red: "C0392B",
  orange: "E67E22",
  yellow: "F39C12",
  green: "27AE60",
  gray: "7F8C8D",
  lightBg: "F0F4F8",
  headerBg: "1B3A5C",
  headerText: "FFFFFF",
  tableBorder: "BDC3C7",
  black: "000000",
  white: "FFFFFF",
};

const border = { style: BorderStyle.SINGLE, size: 1, color: C.tableBorder };
const cellB = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noCellB = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

// ── Helpers ──
const p = (text, opts = {}) => new Paragraph({
  spacing: { before: opts.spaceBefore || 0, after: opts.spaceAfter || 120 },
  alignment: opts.align || AlignmentType.LEFT,
  ...(opts.heading ? { heading: opts.heading } : {}),
  ...(opts.numbering ? { numbering: opts.numbering } : {}),
  ...(opts.pageBreakBefore ? { pageBreakBefore: true } : {}),
  children: typeof text === "string"
    ? [new TextRun({ text, ...opts.run })]
    : text,
});

const bold = (text, opts = {}) => new TextRun({ text, bold: true, ...opts });
const txt = (text, opts = {}) => new TextRun({ text, ...opts });

const headerCell = (text, width) => new TableCell({
  borders: cellB, width: { size: width, type: WidthType.DXA },
  shading: { fill: C.headerBg, type: ShadingType.CLEAR },
  verticalAlign: VerticalAlign.CENTER,
  children: [p([bold(text, { color: C.white, size: 20, font: "Arial" })], { align: AlignmentType.CENTER })],
});

const cell = (content, width, opts = {}) => new TableCell({
  borders: cellB, width: { size: width, type: WidthType.DXA },
  ...(opts.shading ? { shading: { fill: opts.shading, type: ShadingType.CLEAR } } : {}),
  verticalAlign: VerticalAlign.CENTER,
  children: Array.isArray(content) ? content : [p([txt(content, { size: 20, font: "Arial" })], { align: opts.align })],
});

const badgeCell = (text, color, width) => new TableCell({
  borders: cellB, width: { size: width, type: WidthType.DXA },
  shading: { fill: color, type: ShadingType.CLEAR },
  verticalAlign: VerticalAlign.CENTER,
  children: [p([bold(text, { color: C.white, size: 18, font: "Arial" })], { align: AlignmentType.CENTER })],
});

const row = (...cells) => new TableRow({ children: cells });

const table = (colWidths, rows) => new Table({ columnWidths: colWidths, rows });

const bullet = (ref, text, opts = {}) => p(
  typeof text === "string" ? [txt(text, { size: 22, font: "Arial", ...opts })] : text,
  { numbering: { reference: ref, level: 0 } }
);

const numbered = (ref, text) => p(
  [txt(text, { size: 22, font: "Arial" })],
  { numbering: { reference: ref, level: 0 } }
);

const emptyLine = () => p("", { spaceAfter: 60 });

// ── Document ──
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal",
        run: { size: 56, bold: true, color: C.primary, font: "Arial" },
        paragraph: { spacing: { before: 0, after: 200 }, alignment: AlignmentType.CENTER } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: C.primary, font: "Arial" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: C.accent, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, color: C.black, font: "Arial" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bl", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "n1", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "n2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "n3", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "n4", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "n5", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [
    // ─── COVER PAGE ───
    {
      properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      children: [
        p("", { spaceAfter: 2400 }),
        p([bold("KB Indonesia AI FDS", { size: 60, color: C.primary, font: "Arial" })], { align: AlignmentType.CENTER, spaceAfter: 200 }),
        p([bold("Fraud Detection System", { size: 44, color: C.accent, font: "Arial" })], { align: AlignmentType.CENTER, spaceAfter: 100 }),
        p([txt("인도네시아 FDS 전문가 5인 종합 검토 보고서", { size: 28, color: C.gray, font: "Arial" })], { align: AlignmentType.CENTER, spaceAfter: 600 }),
        // Divider line via table
        new Table({
          columnWidths: [9360],
          rows: [row(new TableCell({
            borders: { top: noBorder, bottom: { style: BorderStyle.SINGLE, size: 3, color: C.accent }, left: noBorder, right: noBorder },
            width: { size: 9360, type: WidthType.DXA },
            children: [p("", { spaceAfter: 0 })],
          }))],
        }),
        p("", { spaceAfter: 400 }),
        p([txt("PT Bank KB Bukopin Tbk", { size: 24, color: C.black, font: "Arial" })], { align: AlignmentType.CENTER, spaceAfter: 80 }),
        p([txt("PoC 프로젝트 검토 및 프로덕션 전환 제안서", { size: 22, color: C.gray, font: "Arial" })], { align: AlignmentType.CENTER, spaceAfter: 400 }),
        // Info box
        table([4680, 4680], [
          row(
            cell([p([bold("작성일:", { size: 20 }), txt("  2026년 4월 3일", { size: 20 })], {})], 4680),
            cell([p([bold("버전:", { size: 20 }), txt("  1.0", { size: 20 })], {})], 4680),
          ),
          row(
            cell([p([bold("보안등급:", { size: 20 }), txt("  Confidential", { size: 20, color: C.red })], {})], 4680),
            cell([p([bold("배포대상:", { size: 20 }), txt("  KB Indonesia 경영진", { size: 20 })], {})], 4680),
          ),
        ]),
        p("", { spaceAfter: 600 }),
        p([txt("검토 전문가 패널", { size: 20, bold: true, color: C.gray })], { align: AlignmentType.CENTER, spaceAfter: 100 }),
        p([txt("OJK/PPATK 규제 전문가 | FDS 탐지 로직 전문가 | 결제 시스템 전문가 | 보안/개인정보 전문가 | 은행 운영 전문가", { size: 18, color: C.gray })], { align: AlignmentType.CENTER }),
      ],
    },
    // ─── TOC ───
    {
      properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: {
        default: new Header({ children: [p([txt("KB Indonesia AI FDS — 종합 검토 보고서", { size: 16, color: C.gray, italics: true })], { align: AlignmentType.RIGHT })] }),
      },
      footers: {
        default: new Footer({ children: [p([txt("Confidential — ", { size: 16, color: C.gray }), txt("Page ", { size: 16, color: C.gray }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: C.gray }), txt(" / ", { size: 16, color: C.gray }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: C.gray })], { align: AlignmentType.CENTER })] }),
      },
      children: [
        p([bold("목차", { size: 32, color: C.primary })], { heading: HeadingLevel.TITLE, spaceAfter: 300 }),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
        new Paragraph({ children: [new PageBreak()] }),

        // ─── 1. EXECUTIVE SUMMARY ───
        p([bold("Executive Summary")], { heading: HeadingLevel.HEADING_1 }),
        p([txt("본 보고서는 KB Indonesia (PT Bank KB Bukopin) AI 기반 Fraud Detection System(FDS) PoC 프로젝트에 대해 인도네시아 FDS 전문가 5인이 수행한 종합 검토 결과를 담고 있습니다.", { size: 22 })]),
        emptyLine(),
        p([bold("검토 결론: ", { size: 22, color: C.red }), txt("PoC 기술 시연용으로는 우수하나, 프로덕션 전환까지 최소 12~14개월 소요 예상", { size: 22 })]),
        emptyLine(),

        // Expert summary table
        p([bold("전문가별 종합 평가")], { heading: HeadingLevel.HEADING_2 }),
        table([1800, 2200, 1400, 3960], [
          row(headerCell("전문가", 1800), headerCell("검토 영역", 2200), headerCell("등급", 1400), headerCell("핵심 발견", 3960)),
          row(
            cell("OJK/PPATK\n규제 전문가", 1800, { shading: C.lightBg }),
            cell("인도네시아 금융규제", 2200, { shading: C.lightBg }),
            badgeCell("NON-COMPLIANT", C.red, 1400),
            cell("STR/CTR 보고 전무, goAML 미연동,\nCDD 부재, 결제채널 미분화", 3960, { shading: C.lightBg }),
          ),
          row(
            cell("FDS 탐지\n로직 전문가", 1800),
            cell("사기 탐지 효과성", 2200),
            badgeCell("WEAK", C.orange, 1400),
            cell("QRIS/ATO 규칙 부재, 점수 중복합산,\nDB기본값 불일치, 교차거래 분석 불가", 3960),
          ),
          row(
            cell("결제 시스템\n전문가", 1800, { shading: C.lightBg }),
            cell("BI-FAST/RTGS/QRIS", 2200, { shading: C.lightBg }),
            badgeCell("NON-COMPLIANT", C.red, 1400),
            cell("결제채널 완전 미분화, 채널별\n위험프로파일/임계값 구분 없음", 3960, { shading: C.lightBg }),
          ),
          row(
            cell("보안/개인정보\n전문가", 1800),
            cell("UU PDP, 보안", 2200),
            badgeCell("4 CRITICAL", C.red, 1400),
            cell("API 인증 전무, 국외 데이터 전송,\nDB 미암호화, 프롬프트 인젝션 우회", 3960),
          ),
          row(
            cell("은행 운영\n전문가", 1800, { shading: C.lightBg }),
            cell("운영 프로세스", 2200, { shading: C.lightBg }),
            badgeCell("1.6/10", C.red, 1400),
            cell("케이스 관리 0%, 고객 통지 0%,\nPPATK 보고 0%, 코어뱅킹 연동 0%", 3960, { shading: C.lightBg }),
          ),
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 2. CRITICAL ISSUES ───
        p([bold("CRITICAL 이슈 (즉시 조치 필요)")], { heading: HeadingLevel.HEADING_1 }),
        p([txt("5인 전문가가 공통으로 지적한 즉시 조치가 필요한 최우선 이슈입니다.", { size: 22, color: C.gray, italics: true })]),
        emptyLine(),

        // Critical issue 1
        p([bold("2.1  API 인증/인가 완전 부재")], { heading: HeadingLevel.HEADING_2 }),
        p([bold("심각도: ", { size: 22 }), bold("CRITICAL", { size: 22, color: C.red })]),
        p([txt("현재 모든 API 엔드포인트에 인증이 없습니다. 네트워크 접근 가능한 누구나 규칙 비활성화, 임계값 변경, 거래이력 조회가 가능합니다.", { size: 22 })]),
        bullet("bl", "규칙 점수 변경: PUT /api/rules/{rule_name} — 인증 없이 즉시 적용"),
        bullet("bl", "임계값 조작: PUT /api/conditions/{param_name} — FDS 무력화 가능"),
        bullet("bl", "거래 이력 열람: GET /api/transactions — 전체 분석 결과 노출"),
        p([bold("권고: ", { size: 22, color: C.green }), txt("JWT + RBAC(역할 기반 접근 제어) 즉시 구현", { size: 22 })]),
        emptyLine(),

        // Critical issue 2
        p([bold("2.2  PPATK 보고 체계 전무")], { heading: HeadingLevel.HEADING_2 }),
        p([bold("심각도: ", { size: 22 }), bold("CRITICAL — 법적 의무 불이행", { size: 22, color: C.red })]),
        p([txt("LTKM(현금거래보고), LTKT(의심거래보고) 자동 생성 기능이 전혀 없으며, goAML 시스템 연동도 미구현입니다. UU No. 8/2010에 따라 보고 의무 불이행은 형사 처벌 대상입니다.", { size: 22 })]),
        p([bold("권고: ", { size: 22, color: C.green }), txt("goAML XML 기반 자동 보고 모듈 + 3영업일 기한 관리 시스템 구축", { size: 22 })]),
        emptyLine(),

        // Critical issue 3
        p([bold("2.3  결제 채널 미분화 (BI-FAST/RTGS/SKNBI/QRIS)")], { heading: HeadingLevel.HEADING_2 }),
        p([bold("심각도: ", { size: 22 }), bold("CRITICAL", { size: 22, color: C.red })]),
        p([txt("TransactionType이 3개(domestic/interbank/international)뿐이며, 인도네시아 5대 결제 인프라를 구분하지 못합니다. Fraud Case KB에서 BI-FAST, RTGS, QRIS를 명시적으로 언급하나 시스템은 활용 불가합니다.", { size: 22 })]),
        table([2340, 2340, 2340, 2340], [
          row(headerCell("BI-FAST", 2340), headerCell("RTGS", 2340), headerCell("SKNBI", 2340), headerCell("QRIS", 2340)),
          row(
            cell("실시간 24/7\n건당 250M IDR 한도\nfan-out 사기 선호", 2340),
            cell("실시간 대액이체\n100M+ IDR\n자금세탁 경로", 2340),
            cell("배치 정산\n1일 2~3회\nstructuring 위험", 2340),
            cell("QR 결제\n건당 10M IDR 한도\n가맹점 위조 위험", 2340),
          ),
        ]),
        emptyLine(),

        // Critical issue 4
        p([bold("2.4  UU PDP 국외 데이터 전송 위반")], { heading: HeadingLevel.HEADING_2 }),
        p([bold("심각도: ", { size: 22 }), bold("CRITICAL — 매출액 2% 과징금 리스크", { size: 22, color: C.red })]),
        p([txt("거래 데이터가 OpenAI 미국 서버로 전송되고 있으나, UU PDP 제56조가 요구하는 국외 이전 조건(DPA, SCC, 동의)을 충족하지 못합니다.", { size: 22 })]),
        p([bold("권고: ", { size: 22, color: C.green }), txt("AWS Bedrock(Jakarta/Singapore 리전) 전환 또는 온프레미스 LLM 도입", { size: 22 })]),
        emptyLine(),

        // Critical issue 5
        p([bold("2.5  점수 중복 합산 구조적 결함")], { heading: HeadingLevel.HEADING_2 }),
        p([bold("심각도: ", { size: 22 }), bold("CRITICAL", { size: 22, color: C.red })]),
        p([txt("is_large_amount 조건이 7개 규칙에서 중복 사용되어, 동일 위험 지표가 과대 반영됩니다. SIM swap 거래 시 110점(→100캡)이 산출되는 등 점수 부풀림이 발생합니다.", { size: 22 })]),
        p([bold("권고: ", { size: 22, color: C.green }), txt("카테고리별 MAX 스코어 + 카테고리간 합산 방식으로 전환", { size: 22 })]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 3. REGULATORY COMPLIANCE ───
        p([bold("규제 준수 현황")], { heading: HeadingLevel.HEADING_1 }),
        table([3200, 1800, 1600, 2760], [
          row(headerCell("규제 영역", 3200), headerCell("준수 등급", 1800), headerCell("심각도", 1600), headerCell("핵심 결함", 2760)),
          row(cell("PPATK CTR (현금거래보고)", 3200, { shading: C.lightBg }), badgeCell("PARTIAL", C.orange, 1800), cell("높음", 1600, { shading: C.lightBg }), cell("현금/전자 미구분", 2760, { shading: C.lightBg })),
          row(cell("PPATK STR (의심거래보고)", 3200), badgeCell("NON-COMPLIANT", C.red, 1800), cell("치명적", 1600), cell("보고 체계 전면 부재", 2760)),
          row(cell("goAML 시스템 연동", 3200, { shading: C.lightBg }), badgeCell("NON-COMPLIANT", C.red, 1800), cell("치명적", 1600, { shading: C.lightBg }), cell("연동 없음", 2760, { shading: C.lightBg })),
          row(cell("OJK AML/CFT (POJK 12/2017)", 3200), badgeCell("PARTIAL", C.orange, 1800), cell("높음", 1600), cell("CDD 데이터 부재", 2760)),
          row(cell("BI 결제채널 구분", 3200, { shading: C.lightBg }), badgeCell("NON-COMPLIANT", C.red, 1800), cell("높음", 1600, { shading: C.lightBg }), cell("BI-FAST/RTGS/QRIS 미분화", 2760, { shading: C.lightBg })),
          row(cell("UU PDP (개인정보보호)", 3200), badgeCell("PARTIAL", C.orange, 1800), cell("높음", 1600), cell("국외 전송 통제 미비", 2760)),
          row(cell("FATF Rec.10 CDD", 3200, { shading: C.lightBg }), badgeCell("NON-COMPLIANT", C.red, 1800), cell("치명적", 1600, { shading: C.lightBg }), cell("CDD 연동 없음", 2760, { shading: C.lightBg })),
          row(cell("FATF Rec.16 Wire Transfer", 3200), badgeCell("NON-COMPLIANT", C.red, 1800), cell("높음", 1600), cell("송금인 정보 부족", 2760)),
          row(cell("PEP 심사", 3200, { shading: C.lightBg }), badgeCell("NOT ADDRESSED", C.gray, 1800), cell("높음", 1600, { shading: C.lightBg }), cell("전혀 미구현", 2760, { shading: C.lightBg })),
          row(cell("DTTOT/UN/OFAC 제재목록", 3200), badgeCell("PARTIAL", C.orange, 1800), cell("높음", 1600), cell("국가만, 개인/법인 미지원", 2760)),
          row(cell("고객 차단 통지", 3200, { shading: C.lightBg }), badgeCell("NON-COMPLIANT", C.red, 1800), cell("높음", 1600, { shading: C.lightBg }), cell("통지 체계 없음", 2760, { shading: C.lightBg })),
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 4. DETECTION EFFECTIVENESS ───
        p([bold("FDS 탐지 효과성 분석")], { heading: HeadingLevel.HEADING_1 }),

        p([bold("탐지 갭 (놓치는 사기)")], { heading: HeadingLevel.HEADING_2 }),
        table([2800, 3800, 1200, 1560], [
          row(headerCell("시나리오", 2800), headerCell("탐지 불가 이유", 3800), headerCell("심각도", 1200), headerCell("관련 사례", 1560)),
          row(cell("QRIS/E-Wallet 사기", 2800, { shading: C.lightBg }), cell("QRIS 채널 규칙 없음,\n금액이 25M 미만으로 탐지 불가", 3800, { shading: C.lightBg }), badgeCell("CRITICAL", C.red, 1200), cell("case_011", 1560, { shading: C.lightBg })),
          row(cell("Account Takeover (ATO)", 2800), cell("한도변경/로그인시도/비밀번호\n초기화 관련 필드/규칙 없음", 3800), badgeCell("CRITICAL", C.red, 1200), cell("case_010", 1560)),
          row(cell("인바운드 Mule 패턴", 2800, { shading: C.lightBg }), cell("수신측 다중소스 입금 탐지 불가\n(송금자 관점만 설계)", 3800, { shading: C.lightBg }), badgeCell("HIGH", C.orange, 1200), cell("case_001", 1560, { shading: C.lightBg })),
          row(cell("교차거래 상관분석", 2800), cell("단일거래 독립평가 구조\n거래 간 상관관계 분석 불가", 3800), badgeCell("HIGH", C.orange, 1200), cell("case_003", 1560)),
          row(cell("TBML(무역기반 세탁)", 2800, { shading: C.lightBg }), cell("무역서류 검증 필드 없음\n합법국가(SG,HK) 경유 시 미탐", 3800, { shading: C.lightBg }), badgeCell("MEDIUM", C.yellow, 1200), cell("case_009", 1560, { shading: C.lightBg })),
        ]),
        emptyLine(),

        p([bold("오탐 위험 (정상 거래 차단)")], { heading: HeadingLevel.HEADING_2 }),
        table([2800, 4000, 1200, 1360], [
          row(headerCell("시나리오", 2800), headerCell("오탐 이유", 4000), headerCell("심각도", 1200), headerCell("영향", 1360)),
          row(cell("라마단/THR 시즌", 2800, { shading: C.lightBg }), cell("계절성 미반영, THR 보너스로 인한\n평소 5-10배 거래 증가가 anomaly 트리거", 4000, { shading: C.lightBg }), badgeCell("CRITICAL", C.red, 1200), cell("대량 오탐", 1360, { shading: C.lightBg })),
          row(cell("UMKM 소상공인", 2800), cell("도매상 일 20-30건 거래가 정상이나\nhigh_frequency 규칙 트리거", 4000), badgeCell("HIGH", C.orange, 1200), cell("고객 이탈", 1360)),
          row(cell("기업 급여 일괄지급", 2800, { shading: C.lightBg }), cell("50명 급여 → frequency(25) +\nanomal(20) = 45점으로 경보", 4000, { shading: C.lightBg }), badgeCell("HIGH", C.orange, 1200), cell("업무 차질", 1360, { shading: C.lightBg })),
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 5. SECURITY ASSESSMENT ───
        p([bold("보안 및 개인정보보호 평가")], { heading: HeadingLevel.HEADING_1 }),
        table([800, 3000, 1200, 4360], [
          row(headerCell("#", 800), headerCell("이슈", 3000), headerCell("심각도", 1200), headerCell("조치사항", 4360)),
          row(cell("C1", 800, { shading: C.lightBg }), cell("API 인증/인가 전면 부재", 3000, { shading: C.lightBg }), badgeCell("CRITICAL", C.red, 1200), cell("JWT + RBAC 구현 (2-3일)", 4360, { shading: C.lightBg })),
          row(cell("C2", 800), cell("국외 데이터 전송 통제 미비", 3000), badgeCell("CRITICAL", C.red, 1200), cell("DPA 체결 또는 자체 LLM 전환 (1-4주)", 4360)),
          row(cell("C3", 800, { shading: C.lightBg }), cell("DB 미암호화 (SQLite 평문)", 3000, { shading: C.lightBg }), badgeCell("CRITICAL", C.red, 1200), cell("SQLCipher 또는 PostgreSQL+TDE (3-5일)", 4360, { shading: C.lightBg })),
          row(cell("C4", 800), cell("API 키 런타임 보호 부재", 3000), badgeCell("CRITICAL", C.red, 1200), cell("Secrets Manager 도입 (1-2일)", 4360)),
          row(cell("H1", 800, { shading: C.lightBg }), cell("Rate Limiting 부재", 3000, { shading: C.lightBg }), badgeCell("HIGH", C.orange, 1200), cell("slowapi 적용 (1일)", 4360, { shading: C.lightBg })),
          row(cell("H2", 800), cell("프롬프트 인젝션 우회 가능", 3000), badgeCell("HIGH", C.orange, 1200), cell("Unicode 정규화 + 다국어 필터 (2-3일)", 4360)),
          row(cell("H3", 800, { shading: C.lightBg }), cell("감사 로그 무결성 미보장", 3000, { shading: C.lightBg }), badgeCell("HIGH", C.orange, 1200), cell("해시 체인 + 외부 앵커링 (2-3일)", 4360, { shading: C.lightBg })),
          row(cell("H4", 800), cell("UU PDP 동의/고지 절차 부재", 3000), badgeCell("HIGH", C.orange, 1200), cell("개인정보 처리 동의 절차 구축 (1-2주)", 4360)),
          row(cell("H5", 800, { shading: C.lightBg }), cell("POJK IT 리스크 관리 미준수", 3000, { shading: C.lightBg }), badgeCell("HIGH", C.orange, 1200), cell("IT 리스크 프레임워크 수립 (2-4주)", 4360, { shading: C.lightBg })),
        ]),

        // Positive note
        emptyLine(),
        p([bold("긍정적 평가 사항", { size: 22, color: C.green })]),
        bullet("bl", "sender_account_id, recipient_account_id, device_id, ip_address는 LLM에 미전송 (적절한 PII 보호)"),
        bullet("bl", "transaction_id 마스킹 처리 구현됨"),
        bullet("bl", "memo 필드에 대한 기본적인 sanitize_text 구현됨"),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 6. OPERATIONS READINESS ───
        p([bold("은행 운영 준비도")], { heading: HeadingLevel.HEADING_1 }),
        table([3200, 1200, 1000, 3960], [
          row(headerCell("영역", 3200), headerCell("점수", 1200), headerCell("등급", 1000), headerCell("프로덕션까지 소요 기간", 3960)),
          row(cell("케이스 관리 워크플로우", 3200, { shading: C.lightBg }), badgeCell("1/10", C.red, 1200), cell("심각", 1000, { shading: C.lightBg }), cell("3-4개월", 3960, { shading: C.lightBg })),
          row(cell("고객 대응 (통지/이의제기)", 3200), badgeCell("0/10", C.red, 1200), cell("심각", 1000), cell("2-3개월", 3960)),
          row(cell("PPATK 보고 체계", 3200, { shading: C.lightBg }), badgeCell("1/10", C.red, 1200), cell("심각", 1000, { shading: C.lightBg }), cell("3-5개월", 3960, { shading: C.lightBg })),
          row(cell("내부 통제 (RBAC/감사)", 3200), badgeCell("2/10", C.red, 1200), cell("심각", 1000), cell("2-3개월", 3960)),
          row(cell("운영 연속성", 3200, { shading: C.lightBg }), badgeCell("3/10", C.orange, 1200), cell("미흡", 1000, { shading: C.lightBg }), cell("2-4개월", 3960, { shading: C.lightBg })),
          row(cell("코어뱅킹 연동", 3200), badgeCell("0/10", C.red, 1200), cell("심각", 1000), cell("4-6개월", 3960)),
          row(cell("KPI 및 성과 측정", 3200, { shading: C.lightBg }), badgeCell("2/10", C.orange, 1200), cell("미흡", 1000, { shading: C.lightBg }), cell("1-2개월", 3960, { shading: C.lightBg })),
          row(cell("비용 최적화", 3200), badgeCell("4/10", C.yellow, 1200), cell("보통", 1000), cell("1-2개월", 3960)),
        ]),
        emptyLine(),
        p([bold("종합 운영 준비도: ", { size: 24, color: C.red }), bold("1.6 / 10 (PoC 수준)", { size: 24, color: C.red })], { align: AlignmentType.CENTER }),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 7. STRENGTHS ───
        p([bold("PoC 강점 (전문가 공통 인정)")], { heading: HeadingLevel.HEADING_1 }),
        p([txt("리뷰 전문가 5인이 공통으로 긍정 평가한 사항입니다.", { size: 22, color: C.gray, italics: true })]),
        emptyLine(),
        table([3200, 6160], [
          row(headerCell("항목", 3200), headerCell("평가", 6160)),
          row(cell([p([bold("당근페이 3계층 패턴", { size: 20 })])], 3200, { shading: C.lightBg }), cell("Condition → Rule → Policy 충실 구현, 로직과 설정 분리 우수", 6160, { shading: C.lightBg })),
          row(cell([p([bold("XML 구조화 프롬프트", { size: 20 })])], 3200), cell("<role>, <evaluation_flow>, <evaluation_criteria> 등 정확한 패턴 적용", 6160)),
          row(cell([p([bold("수동 RAG 파이프라인", { size: 20 })])], 3200, { shading: C.lightBg }), cell("Retrieve + Prompt + API 수동 조합 (당근페이 Step 3)", 6160, { shading: C.lightBg })),
          row(cell([p([bold("Fraud Case KB 품질", { size: 20 })])], 3200), cell("12건 인도네시아 특화 사례 (BRI, BCA, Mandiri, BI-FAST, RTGS)", 6160)),
          row(cell([p([bold("동적 규칙 관리", { size: 20 })])], 3200, { shading: C.lightBg }), cell("DB 기반 실시간 점수/임계값/정책 조정 + 감사 로그", 6160, { shading: C.lightBg })),
          row(cell([p([bold("비용 최적화 설계", { size: 20 })])], 3200), cell("룰엔진 1차 필터링 후 10-20%만 LLM 호출", 6160)),
          row(cell([p([bold("LLM Fallback 처리", { size: 20 })])], 3200, { shading: C.lightBg }), cell("OpenAI 장애 시 룰엔진 단독 판정, confidence 기반 우선순위", 6160, { shading: C.lightBg })),
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 8. ROADMAP ───
        p([bold("프로덕션 전환 로드맵")], { heading: HeadingLevel.HEADING_1 }),

        p([bold("Phase 0: 즉시 수정 (1~2주)")], { heading: HeadingLevel.HEADING_2 }),
        table([600, 4200, 1200, 1800, 1560], [
          row(headerCell("#", 600), headerCell("작업", 4200), headerCell("공수", 1200), headerCell("담당", 1800), headerCell("규제 근거", 1560)),
          row(cell("1", 600, { shading: C.lightBg }), cell("API 인증/인가(JWT+RBAC) 구현", 4200, { shading: C.lightBg }), cell("2-3일", 1200, { shading: C.lightBg }), cell("개발", 1800, { shading: C.lightBg }), cell("POJK 38/2016", 1560, { shading: C.lightBg })),
          row(cell("2", 600), cell("DB fallback 기본값 통일", 4200), cell("1일", 1200), cell("개발", 1800), cell("-", 1560)),
          row(cell("3", 600, { shading: C.lightBg }), cell("감사 로그에 변경자(operator) 추가", 4200, { shading: C.lightBg }), cell("1일", 1200, { shading: C.lightBg }), cell("개발", 1800, { shading: C.lightBg }), cell("SE OJK 14/2023", 1560, { shading: C.lightBg })),
          row(cell("4", 600), cell("PII 마스킹 강화 (memo PII 감지)", 4200), cell("1일", 1200), cell("개발", 1800), cell("UU PDP", 1560)),
          row(cell("5", 600, { shading: C.lightBg }), cell("프롬프트 인젝션 방어 강화", 4200, { shading: C.lightBg }), cell("2일", 1200, { shading: C.lightBg }), cell("개발", 1800, { shading: C.lightBg }), cell("-", 1560, { shading: C.lightBg })),
        ]),
        emptyLine(),

        p([bold("Phase 1: 규제 필수 (1~3개월)")], { heading: HeadingLevel.HEADING_2 }),
        table([600, 4200, 1200, 1800, 1560], [
          row(headerCell("#", 600), headerCell("작업", 4200), headerCell("공수", 1200), headerCell("담당", 1800), headerCell("규제 근거", 1560)),
          row(cell("6", 600, { shading: C.lightBg }), cell("PPATK LTKM/LTKT + goAML 보고 모듈", 4200, { shading: C.lightBg }), cell("High", 1200, { shading: C.lightBg }), cell("컴플라이언스\n+개발", 1800, { shading: C.lightBg }), cell("UU 8/2010", 1560, { shading: C.lightBg })),
          row(cell("7", 600), cell("결제채널(BI-FAST/RTGS/QRIS) 분화", 4200), cell("Medium", 1200), cell("개발", 1800), cell("PBI 23/6/2021", 1560)),
          row(cell("8", 600, { shading: C.lightBg }), cell("Transaction 모델 필수 필드 확장", 4200, { shading: C.lightBg }), cell("Medium", 1200, { shading: C.lightBg }), cell("개발", 1800, { shading: C.lightBg }), cell("-", 1560, { shading: C.lightBg })),
          row(cell("9", 600), cell("데이터 거주성 해결 (Bedrock 전환)", 4200), cell("Medium", 1200), cell("개발+인프라", 1800), cell("PP 71/2019", 1560)),
          row(cell("10", 600, { shading: C.lightBg }), cell("PEP/제재 목록 연동 인터페이스", 4200, { shading: C.lightBg }), cell("Medium", 1200, { shading: C.lightBg }), cell("컴플라이언스\n+개발", 1800, { shading: C.lightBg }), cell("FATF Rec.12", 1560, { shading: C.lightBg })),
        ]),
        emptyLine(),

        p([bold("Phase 2: 운영 필수 (2~4개월)")], { heading: HeadingLevel.HEADING_2 }),
        table([600, 4200, 1200, 1800, 1560], [
          row(headerCell("#", 600), headerCell("작업", 4200), headerCell("공수", 1200), headerCell("담당", 1800), headerCell("규제 근거", 1560)),
          row(cell("11", 600, { shading: C.lightBg }), cell("케이스 관리 시스템 (큐/배정/조사/종결)", 4200, { shading: C.lightBg }), cell("High", 1200, { shading: C.lightBg }), cell("개발", 1800, { shading: C.lightBg }), cell("SE OJK 29/2022", 1560, { shading: C.lightBg })),
          row(cell("12", 600), cell("TP/FP 마킹 + 피드백 루프", 4200), cell("Medium", 1200), cell("FDS운영\n+개발", 1800), cell("-", 1560)),
          row(cell("13", 600, { shading: C.lightBg }), cell("고객 통지 + HOLD/BLOCK/DELAY 분화", 4200, { shading: C.lightBg }), cell("Medium", 1200, { shading: C.lightBg }), cell("개발+CS", 1800, { shading: C.lightBg }), cell("SE OJK 29/2022", 1560, { shading: C.lightBg })),
          row(cell("14", 600), cell("Maker-Checker 규칙 변경 프로세스", 4200), cell("Medium", 1200), cell("개발", 1800), cell("POJK 18/2016", 1560)),
          row(cell("15", 600, { shading: C.lightBg }), cell("SQLite → PostgreSQL 전환", 4200, { shading: C.lightBg }), cell("Medium", 1200, { shading: C.lightBg }), cell("인프라", 1800, { shading: C.lightBg }), cell("-", 1560, { shading: C.lightBg })),
        ]),
        emptyLine(),

        p([bold("Phase 3: 코어뱅킹 연동 (4~6개월)")], { heading: HeadingLevel.HEADING_2 }),
        numbered("n3", "CBS(T24) 연동 — 거래 이벤트 실시간 수신 + 차단/보류 실행"),
        numbered("n3", "BI-FAST Fast-Path — 룰엔진 단독 판정 (LLM 비동기 사후 평가)"),
        numbered("n3", "계좌 정보 조회 + 동결 연동"),
        numbered("n3", "수취인 블랙리스트 실시간 동기화"),
        emptyLine(),

        p([bold("Phase 4: 고도화 (6~12개월)")], { heading: HeadingLevel.HEADING_2 }),
        numbered("n4", "시간 윈도우 기반 velocity 엔진 (Redis 기반)"),
        numbered("n4", "네트워크 분석 (계좌간 자금흐름 그래프)"),
        numbered("n4", "전통 ML 모델 도입 (XGBoost) + LLM은 설명 생성에 한정"),
        numbered("n4", "온프레미스 LLM 파일럿 (Llama 3/Qwen2)"),
        numbered("n4", "Fraud Case KB 확대 (12건 → 30건+)"),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 9. COST ESTIMATION ───
        p([bold("비용 추정")], { heading: HeadingLevel.HEADING_1 }),
        table([3800, 2780, 2780], [
          row(headerCell("항목", 3800), headerCell("현재 (PoC)", 2780), headerCell("프로덕션 (월)", 2780)),
          row(cell("LLM API (GPT-4o)", 3800, { shading: C.lightBg }), cell("테스트 수준", 2780, { shading: C.lightBg }), cell("$1,300 ~ $5,200", 2780, { shading: C.lightBg })),
          row(cell("LLM API (GPT-4o-mini 전환 시)", 3800), cell("-", 2780), cell("$200 ~ $800 (85% 절감)", 2780)),
          row(cell("인프라 (PostgreSQL, Redis, ECS)", 3800, { shading: C.lightBg }), cell("무료", 2780, { shading: C.lightBg }), cell("$700 ~ $2,500", 2780, { shading: C.lightBg })),
          row(cell("FDS 분석관 인력 (25~85명, 3교대)", 3800), cell("-", 2780), cell("$30,000 ~ $60,000", 2780)),
          row(cell([p([bold("총 월 운영 비용 (추정)", { size: 20, color: C.primary })])], 3800, { shading: "D5E8F0" }), cell([p([bold("-", { size: 20 })])], 2780, { shading: "D5E8F0" }), cell([p([bold("$32,200 ~ $68,500", { size: 20, color: C.primary })])], 2780, { shading: "D5E8F0" })),
        ]),
        emptyLine(),
        p([txt("* 일 50,000~100,000건 거래 기준, 인도네시아 인건비 적용", { size: 18, color: C.gray, italics: true })]),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 10. RECOMMENDATIONS ───
        p([bold("최우선 조치 권고 (Top 5)")], { heading: HeadingLevel.HEADING_1 }),
        table([600, 3600, 3000, 2160], [
          row(headerCell("#", 600), headerCell("조치", 3600), headerCell("사유", 3000), headerCell("관련 규정", 2160)),
          row(cell([p([bold("1", { size: 22, color: C.red })])], 600, { shading: C.lightBg }), cell([p([bold("API 인증/인가(RBAC) 구현", { size: 20 })])], 3600, { shading: C.lightBg }), cell("누구나 모든 API 접근/\n규칙 변경 가능", 3000, { shading: C.lightBg }), cell("POJK 38/2016\nSE OJK 14/2023", 2160, { shading: C.lightBg })),
          row(cell([p([bold("2", { size: 22, color: C.red })])], 600), cell([p([bold("PPATK 보고 모듈 구현", { size: 20 })])], 3600), cell("법적 의무 불이행은\n은행 인가 리스크", 3000), cell("UU 8/2010\nPPATK 8/2022", 2160)),
          row(cell([p([bold("3", { size: 22, color: C.orange })])], 600, { shading: C.lightBg }), cell([p([bold("케이스 관리 + TP/FP 마킹", { size: 20 })])], 3600, { shading: C.lightBg }), cell("탐지 후 처리 워크플로우\n없으면 FDS 무용지물", 3000, { shading: C.lightBg }), cell("SE OJK 29/2022", 2160, { shading: C.lightBg })),
          row(cell([p([bold("4", { size: 22, color: C.orange })])], 600), cell([p([bold("고객 통지 + HOLD 액션", { size: 20 })])], 3600), cell("거래 차단 시 고객\n통보 의무 미이행", 3000), cell("SE OJK 29/2022\nUU PDP 27/2022", 2160)),
          row(cell([p([bold("5", { size: 22, color: C.orange })])], 600, { shading: C.lightBg }), cell([p([bold("데이터 거주성 해결", { size: 20 })])], 3600, { shading: C.lightBg }), cell("OpenAI API 직접 사용은\n국외 데이터 이전", 3000, { shading: C.lightBg }), cell("PP 71/2019\nPOJK 38/2016", 2160, { shading: C.lightBg })),
        ]),

        emptyLine(),
        emptyLine(),

        // ─── CLOSING ───
        p([txt("본 보고서는 KB Indonesia AI FDS PoC 프로젝트의 프로덕션 전환을 위한 전문가 검토 결과를 종합한 것입니다. PoC의 기술적 기반은 우수하나, 인도네시아 금융 규제 환경과 은행 운영 실무를 고려할 때 상기 로드맵에 따른 체계적 보강이 필수적입니다.", { size: 22 })]),
        emptyLine(),
        p([bold("— 인도네시아 FDS 전문가 5인 패널", { size: 22, color: C.gray, italics: true })], { align: AlignmentType.RIGHT }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "/Users/a1654530/Desktop/agent/aifds/KB_Indonesia_AI_FDS_전문가검토_제안서.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Generated:", outPath);
});
