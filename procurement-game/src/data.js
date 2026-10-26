// ── 캠페인 데이터 ─────────────────────────────────────────────
// 모든 지역 상황·제품·수치는 게임 진행을 위해 만든 가상의 설정입니다.
// 제품 배열: [이름, 가격(코인), 성능, 연 유지비(코인), 납기(일), 특징]
const PRI = {
  safety: { n: '안전시설 우선', icon: '🛡', cap: .85, d: '사업비 대부분을 핵심 시설 구매에 씁니다.' },
  comfort: { n: '편의시설 우선', icon: '🪑', cap: .62, d: '쉼터·벤치 같은 편의시설을 함께 갖춥니다.' },
  upkeep: { n: '유지관리 예산 확보', icon: '🔧', cap: .72, d: '고장·점검에 대비해 관리 예산을 남깁니다.' }
};
const TYPES = ['A형 경제형', 'B형 균형형', 'C형 고급형'];

const REGIONS = [
{ id: 'seoul', name: '서울', full: '서울특별시', town: '한빛동 도심 사거리', mission: '무더운 도심에 쉼터 조성', item: '스마트 그늘막', icon: '⛱',
  lat: 37.57, lon: 126.98, color: '#e0875f', land: '#c9c4b4', sky: ['#fff4dc', '#f2dcc0'], wx: 'heat', weather: '☀ 폭염 · 35°',
  problem: '그늘 없는 횡단보도', fixed: '시원한 그늘 아래 신호 대기', before: '뜨거운 햇볕 아래서 신호를 기다리고 있어요.', after: '그늘막이 펼쳐지고 사람들이 시원하게 신호를 기다려요.',
  budget: 60, focus: 'comfort', second: 'safety', perf: '그늘·자동 개폐 성능', min: 70,
  pt: { safety: '횡단보도 안전 표지부터 정비하고 남은 돈으로 그늘막을 사요.', comfort: '그늘막과 함께 앉아 쉴 벤치도 마련해요.', upkeep: '센서 고장에 대비해 관리비를 남겨둬요.' },
  event: { name: '폭염 특보', icon: '🌡', d: 7, hit: '폭염 특보가 내려졌어요! 그늘막이 아직 없어요.' },
  products: [['기본 접이식 그늘막', 22, 62, 4, 3, '수동 개폐 · 바람에 약함'], ['스마트 자동개폐 그늘막', 32, 82, 2, 6, '풍속 센서 · 자동 접힘'], ['대형 태양광 스마트 그늘막', 46, 95, 2, 12, '미스트 · 조명 내장']],
  residents: [
    { k: 'chief', n: '횡단보도 어르신', line: '신호 기다리는 2분이 너무 뜨거워요. 그늘에서 잠깐 앉아 쉬면 좋겠어요.', clue: '그늘 + 앉을 자리(편의) 필요' },
    { k: 'sorang', n: '동네 돌봄 도우미', line: '바람 센 날 그늘막이 넘어지면 위험해요. 바람에 알아서 접히는 게 좋겠어요.', clue: '성능 70 이상 · 자동 개폐' },
    { k: 'mongdol', n: '편의점 사장님', line: '다음 주쯤 폭염 특보가 온대요. 일주일 안에는 설치돼야 해요!', clue: '폭염 특보 D-7' } ],
  thanks: '그늘 아래서 기다리니 살 것 같아요!' },

{ id: 'busan', name: '부산', full: '부산광역시', town: '물빛 항구 선착장', mission: '항구 주변 안전 확보', item: '구명장비·안전시설', icon: '🛟',
  lat: 35.18, lon: 129.08, color: '#4f8fb8', land: '#d8cfb3', sky: ['#e3f1f6', '#c9e0ea'], wx: 'wind', weather: '🌬 강풍 · 파도 2m',
  problem: '난간 없는 부두 가장자리', fixed: '구명장비와 난간 완비', before: '부두 가장자리에 난간도 구명장비도 없어요.', after: '튼튼한 난간과 구명장비함이 생겨 안심하고 산책해요.',
  budget: 70, focus: 'safety', second: 'upkeep', perf: '안전 성능', min: 75,
  pt: { safety: '추락 방지 난간과 구명장비를 가장 먼저 갖춰요.', comfort: '산책로 벤치와 조명도 함께 놓아요.', upkeep: '바닷바람 부식에 대비해 점검비를 남겨요.' },
  event: { name: '강풍·높은 파도', icon: '🌊', d: 5, hit: '강풍과 함께 높은 파도가 몰려와요!' },
  products: [['기본 구명환 세트', 20, 68, 3, 2, '구명환 4개 · 거치대'], ['구명장비함+안전난간', 38, 85, 2, 4, '구명조끼·구명환 · 난간 30m'], ['스마트 감지 안전펜스', 58, 96, 3, 9, '추락 감지 · 자동 경보']],
  residents: [
    { k: 'sora', n: '어촌계장 소라대감', line: '밤낚시 손님이 많은데 부두 끝에 난간이 하나도 없어. 사람이 빠지면 큰일이야.', clue: '추락 방지 = 안전 최우선' },
    { k: 'mongdol', n: '항구 관리인', line: '구명환만 걸어두면 소용없어요. 난간까지 갖춘 안전 성능 75 이상이 필요해요.', clue: '성능 75 이상' },
    { k: 'jacheong', n: '수산시장 상인', line: '닷새 뒤에 강풍 예보가 있어요. 그 전에 설치돼야 해요.', clue: '강풍 D-5' } ],
  thanks: '이제 아이들과 부두 산책도 안심이에요!' },

{ id: 'daegu', name: '대구', full: '대구광역시', town: '달구벌 골목 상가', mission: '폭염에 취약한 거리 개선', item: '냉방 쉼터', icon: '❄',
  lat: 35.87, lon: 128.6, color: '#e06a4f', land: '#d9c39d', sky: ['#ffe9cf', '#f6c9a5'], wx: 'heat', weather: '☀ 폭염 경보 · 38°',
  problem: '쉴 곳 없는 폭염 거리', fixed: '시원한 냉방 쉼터 운영', before: '어르신들이 뜨거운 골목에서 숨을 고르고 있어요.', after: '냉방 쉼터에 모여 시원한 물을 마시며 쉬어요.',
  budget: 80, focus: 'safety', second: 'comfort', perf: '냉방 성능', min: 72,
  pt: { safety: '온열질환을 막는 냉방 성능에 예산을 집중해요.', comfort: '쉼터 옆에 그늘 벤치와 음수대도 놓아요.', upkeep: '여름 전기료와 점검비를 따로 남겨요.' },
  event: { name: '폭염 경보', icon: '🔥', d: 4, hit: '최고 38도! 폭염 경보가 발령됐어요.' },
  products: [['이동식 선풍기 쉼터', 26, 60, 5, 1, '천막 + 대형 선풍기'], ['단열 냉방 쉼터', 44, 80, 3, 6, '단열 패널 · 에어컨'], ['모듈형 고효율 냉방 쉼터', 60, 92, 2, 3, '재고 보유 · 빠른 조립']],
  residents: [
    { k: 'chief', n: '골목 경로회장', line: '선풍기 바람은 뜨거운 바람이야. 진짜 시원한 냉방(성능 72 이상)이 필요해.', clue: '성능 72 이상 · 건강 = 안전' },
    { k: 'sorang', n: '방문 간호 도우미', line: '나흘 뒤 폭염 경보래요. 늦게 오는 제품은 소용없어요!', clue: '폭염 경보 D-4 · 납기 중요' },
    { k: 'mongdol', n: '골목 상인', line: '값이 좀 나가도 빨리 조립되는 제품이 있다던데요?', clue: '빠른 납기 제품 확인' } ],
  thanks: '쉼터 안이 정말 시원해요. 고마워요!' },

{ id: 'incheon', name: '인천', full: '인천광역시', town: '바닷바람 언덕길', mission: '비 오는 항구길의 미끄럼 방지', item: '미끄럼 방지 포장재', icon: '🧱',
  lat: 37.46, lon: 126.62, color: '#5b8f9e', land: '#bfc9bf', sky: ['#e2eaee', '#c8d4da'], wx: 'rain', weather: '☂ 비 · 18°',
  problem: '미끄러운 비탈길', fixed: '논슬립 포장 완료', before: '비에 젖은 비탈길이 반들반들 미끄러워요.', after: '거친 논슬립 포장 위를 안심하고 걸어가요.',
  budget: 60, focus: 'safety', second: 'upkeep', perf: '미끄럼 저항', min: 70,
  pt: { safety: '넘어지지 않는 포장 성능에 집중해요.', comfort: '비 피할 작은 차양도 함께 만들어요.', upkeep: '보수 공사 비용을 미리 남겨둬요.' },
  event: { name: '장마 시작', icon: '🌧', d: 6, hit: '장마가 시작됐어요. 길이 더 미끄러워요!' },
  products: [['미끄럼방지 페인트', 18, 70, 6, 2, '저렴 · 1년마다 재도색'], ['논슬립 블록 포장', 30, 84, 2, 5, '오래가는 거친 블록'], ['투수성 고급 포장', 46, 93, 1, 10, '빗물 흡수 · 시공 김']],
  residents: [
    { k: 'mongdol', n: '항구 배달원', line: '비만 오면 오토바이도 사람도 미끄러져요. 미끄럼 저항 70은 넘어야 해요.', clue: '성능 70 이상 · 안전 최우선' },
    { k: 'chief', n: '언덕 위 주민', line: '페인트는 해마다 다시 칠해야 한다더라. 유지비도 꼭 봐줘.', clue: '유지비 높은 제품 주의' },
    { k: 'jacheong', n: '수산물 가게 주인', line: '엿새 뒤면 장마래요. 그 전에 끝나면 좋겠어요.', clue: '장마 D-6' } ],
  thanks: '비 오는 날에도 미끄럽지 않아요!' },

{ id: 'gwangju', name: '광주', full: '광주광역시', town: '빛고을 통학 골목', mission: '어두운 골목길 밝히기', item: '태양광 LED 가로등', icon: '💡',
  lat: 35.16, lon: 126.85, color: '#e8b04a', land: '#9fb39b', sky: ['#c2cfe0', '#9eb0cc'], wx: 'night', weather: '☾ 해 진 뒤 · 17°',
  problem: '가로등 없는 통학로', fixed: '환하게 켜진 LED 가로등', before: '아이들이 어두운 골목 앞에서 발걸음을 멈췄어요.', after: '골목 전체가 환해지고 아이들이 집으로 걸어가요.',
  budget: 60, focus: 'safety', second: 'upkeep', perf: '밝기', min: 80,
  pt: { safety: '아이들 통학 안전을 위해 밝기에 집중해요.', comfort: '골목 벤치와 꽃화분도 함께 놓아요.', upkeep: '전기료·전구 교체비를 남겨둬요.' },
  event: { name: '개학 · 짧아진 해', icon: '🌙', d: 8, hit: '개학했어요! 해가 일찍 져서 하굣길이 깜깜해요.' },
  products: [['일반 전기식 가로등', 20, 78, 6, 3, '밝음 · 전기료 높음'], ['태양광 LED 가로등', 34, 86, 1, 6, '낮에 충전 · 전기료 0'], ['스마트 조도 태양광 가로등', 50, 95, 1, 12, '사람 감지 · 밝기 조절']],
  residents: [
    { k: 'sorang', n: '학교 앞 돌봄 도우미', line: '아이들이 이 길로 학교에 다녀요. 밝기 80 이상은 돼야 안심이에요.', clue: '밝기 80 이상 · 안전 최우선' },
    { k: 'chief', n: '골목 반장', line: '가로등도 좋지만 전기료가 걱정이에요. 매달 나가는 돈도 봐주세요.', clue: '전기료(유지비) 부담' },
    { k: 'mongdol', n: '문구점 사장님', line: '여드레 뒤 개학이에요. 그때까지는 불이 켜져야 해요.', clue: '개학 D-8' } ],
  thanks: '길이 밝아져서 이제 안심이에요!' },

{ id: 'daejeon', name: '대전', full: '대전광역시', town: '한밭 작은도서관', mission: '오래된 도서관 개선', item: '정보검색·독서 설비', icon: '📚',
  lat: 36.35, lon: 127.38, color: '#7c74c4', land: '#b9c9a6', sky: ['#eef0f8', '#d9def0'], wx: 'clear', weather: '⛅ 맑음 · 21°',
  problem: '낡고 텅 빈 도서관 마당', fixed: '북적이는 스마트 도서관', before: '고장 난 검색대 때문에 책을 찾기 어려워요.', after: '정보검색 키오스크와 독서 부스에 사람들이 모였어요.',
  budget: 70, focus: 'comfort', second: 'upkeep', perf: '검색·독서 환경', min: 70,
  pt: { safety: '낡은 전기 설비 교체에 집중해요.', comfort: '편히 앉아 읽는 독서 공간을 함께 꾸며요.', upkeep: '기기 수리·소프트웨어 관리비를 남겨요.' },
  event: { name: '독서주간 개막', icon: '📖', d: 10, hit: '독서주간이 시작됐어요. 손님이 몰려와요!' },
  products: [['중고 PC 묶음', 22, 58, 5, 2, '느린 검색 · 잦은 고장'], ['검색 키오스크+독서부스', 40, 80, 2, 7, '도서 위치 안내 · 1인 부스'], ['미디어 라운지 패키지', 58, 94, 3, 14, '대형 화면 · 맞춤 가구']],
  residents: [
    { k: 'jacheong', n: '도서관 사서', line: '책을 찾아도 앉아서 읽을 곳이 없어요. 편안한 독서 공간이 제일 필요해요.', clue: '편의시설(독서 공간) 우선' },
    { k: 'sora', n: '책 읽는 할아버지', line: '검색이 느려 답답해. 검색·독서 환경 점수 70은 넘어야지.', clue: '성능 70 이상' },
    { k: 'sorang', n: '방과후 선생님', line: '열흘 뒤 독서주간이에요. 그 전에 준비되면 아이들이 좋아할 거예요.', clue: '독서주간 D-10' } ],
  thanks: '책 찾기가 쉬워지고 앉을 곳도 생겼어요!' },

{ id: 'ulsan', name: '울산', full: '울산광역시', town: '태화 산업단지', mission: '산업단지 화재 위험 줄이기', item: '화재감지·경보시설', icon: '🚨',
  lat: 35.54, lon: 129.31, color: '#d0533f', land: '#b8bcb0', sky: ['#efe9e2', '#d8d2ca'], wx: 'smoke', weather: '🍂 건조 · 습도 22%',
  problem: '감지기 없는 공장 지붕', fixed: '연동형 화재 경보 가동', before: '공장 지붕 위로 연기가 피어올라도 아무도 몰라요.', after: '감지기와 경보등이 연결돼 즉시 대피 안내가 나와요.',
  budget: 90, focus: 'safety', second: 'upkeep', perf: '감지·경보 성능', min: 80,
  pt: { safety: '빠른 감지와 경보에 예산을 집중해요.', comfort: '노동자 휴게실 정비도 함께 해요.', upkeep: '정기 점검·배터리 교체비를 남겨요.' },
  event: { name: '건조 특보', icon: '🔥', d: 5, hit: '건조 특보! 작은 불씨도 크게 번질 수 있어요.' },
  products: [['단독형 연기감지기', 30, 66, 3, 2, '개별 경보 · 연동 안 됨'], ['무선 연동 감지·경보', 52, 86, 2, 5, '동시 경보 · 대피 안내'], ['통합 관제 화재 시스템', 74, 97, 3, 10, '관제실 · 자동 신고']],
  residents: [
    { k: 'mongdol', n: '공장 반장', line: '한 곳에서 불이 나면 단지 전체가 알아야 해요. 연동 경보(성능 80 이상)가 필요해요.', clue: '성능 80 이상 · 안전 최우선' },
    { k: 'chief', n: '경비 아저씨', line: '감지기 배터리가 다 되면 무용지물이야. 점검비도 생각해 둬.', clue: '유지관리 중요' },
    { k: 'sora', n: '산단 안전관리자', line: '닷새 뒤 건조 특보 예보가 있소. 서둘러야 하오.', clue: '건조 특보 D-5' } ],
  thanks: '경보가 울리면 모두 함께 대피할 수 있어요!' },

{ id: 'sejong', name: '세종', full: '세종특별자치시', town: '새롬 초등학교 앞', mission: '학교 앞 보행안전 확보', item: '스마트 횡단보도', icon: '🚸',
  lat: 36.56, lon: 127.26, color: '#f0c24c', land: '#a9c3a0', sky: ['#eaf3f5', '#cfe2e6'], wx: 'clear', weather: '⛅ 맑음 · 20°',
  problem: '신호 없는 학교 앞 횡단보도', fixed: '빛나는 스마트 횡단보도', before: '차들이 쌩쌩 달려 아이들이 길을 건너기 무서워해요.', after: '바닥 신호등이 켜지고 차들이 멈춰 서요.',
  budget: 70, focus: 'safety', second: 'comfort', perf: '보행 안전 성능', min: 75,
  pt: { safety: '아이들 보행 안전에 예산을 집중해요.', comfort: '보호자 대기 쉼터도 함께 만들어요.', upkeep: '신호기 점검비를 남겨둬요.' },
  event: { name: '새 학기 개학', icon: '🎒', d: 6, hit: '개학 날! 아이들이 한꺼번에 등교해요.' },
  products: [['노면 도색+표지판', 18, 64, 4, 2, '도색 · 표지판 2개'], ['LED 바닥신호+음성안내', 40, 85, 2, 5, '바닥 신호등 · 음성 경고'], ['AI 보행감지 횡단보도', 54, 96, 2, 6, '보행자 감지 · 차량 경고']],
  residents: [
    { k: 'sorang', n: '녹색어머니회', line: '휴대폰 보며 걷는 아이들도 신호를 볼 수 있게 바닥에 신호가 있으면 해요.', clue: '보행 안전 최우선 · 바닥 신호' },
    { k: 'chief', n: '등굣길 지킴이 할아버지', line: '페인트만 칠해선 안 돼. 보행 안전 성능 75는 넘어야지.', clue: '성능 75 이상' },
    { k: 'jacheong', n: '학교 앞 문구점', line: '엿새 뒤 개학이에요! 그 전에 꼭 완성해 주세요.', clue: '개학 D-6' } ],
  thanks: '바닥에 불이 들어와서 아이들이 잘 멈춰요!' },

{ id: 'gyeonggi', name: '경기', full: '경기도', town: '새빛 신도시 정류장', mission: '대중교통 이용환경 개선', item: '스마트 버스정류장', icon: '🚌',
  lat: 37.28, lon: 127.38, color: '#4c9a7a', land: '#b4c9a8', sky: ['#e8f0f4', '#cddce6'], wx: 'cold', weather: '❄ 한파 · -9°',
  problem: '바람 막을 곳 없는 정류장', fixed: '따뜻한 스마트 정류장', before: '찬바람 속에서 버스가 언제 올지 몰라 발을 동동 굴러요.', after: '온열 의자에 앉아 도착 정보를 보며 버스를 기다려요.',
  budget: 70, focus: 'comfort', second: 'safety', perf: '대기 환경 성능', min: 70,
  pt: { safety: '어두운 정류장 조명과 CCTV에 집중해요.', comfort: '온열 의자와 바람막이 같은 편의시설을 갖춰요.', upkeep: '전광판 통신비·수리비를 남겨요.' },
  event: { name: '한파 특보', icon: '🥶', d: 7, hit: '영하 9도 한파! 정류장이 꽁꽁 얼었어요.' },
  products: [['기본 차양 정류장', 20, 55, 3, 2, '지붕 · 벤치'], ['스마트 정류장', 40, 82, 2, 6, '온열 의자 · 도착 안내 · 바람막이'], ['밀폐형 냉난방 정류장', 62, 94, 5, 9, '냉난방기 · 전기료 높음']],
  residents: [
    { k: 'chief', n: '출근길 어르신', line: '버스가 언제 오는지만 알아도 덜 춥지. 따뜻하게 앉을 곳이 제일 필요해.', clue: '편의시설(온열 의자) 우선' },
    { k: 'jacheong', n: '통학 대학생', line: '지붕만 있는 정류장은 바람이 숭숭 들어와요. 성능 70 이상이면 좋겠어요.', clue: '성능 70 이상' },
    { k: 'mongdol', n: '마을버스 기사', line: '일주일 뒤 한파 특보가 온대요. 그 전에 설치해 주세요.', clue: '한파 특보 D-7' } ],
  thanks: '버스 기다리는 시간이 따뜻해졌어요!' },

{ id: 'gangwon', name: '강원', full: '강원특별자치도', town: '설악 산간마을', mission: '폭설 전 산간마을 도로 확보', item: '제설장비', icon: '🚜',
  lat: 37.75, lon: 128.25, color: '#6d9fd0', land: '#e9eef0', sky: ['#e7eef5', '#cbd9e8'], wx: 'snow', weather: '❄ 눈 · -6°',
  problem: '눈에 막힐 산골 도로', fixed: '제설된 산골 도로', before: '눈이 쌓이면 마을로 들어오는 유일한 길이 막혀요.', after: '제설차가 길을 열고 차량이 다시 다녀요.',
  budget: 90, focus: 'safety', second: 'upkeep', perf: '제설 능력', min: 75,
  pt: { safety: '고립을 막는 제설 능력에 집중해요.', comfort: '버스 대기용 난방 쉼터도 함께 지어요.', upkeep: '염화칼슘·연료비를 남겨둬요.' },
  event: { name: '대설 경보', icon: '🌨', d: 3, hit: '대설 경보! 하룻밤에 눈이 50cm나 쌓였어요.' },
  products: [['소형 제설기', 30, 70, 3, 1, '즉시 출고 · 좁은 길용'], ['트럭 부착 삽날+살포기', 50, 84, 3, 7, '주문 생산 · 성능 우수'], ['다목적 제설 차량', 70, 92, 2, 2, '비축 재고 · 즉시 투입']],
  residents: [
    { k: 'chief', n: '산간마을 이장', line: '눈 오면 병원 가는 길이 끊겨. 제설 능력 75는 돼야 큰길까지 뚫지.', clue: '성능 75 이상 · 안전 최우선' },
    { k: 'sora', n: '마을 버스 기사', line: '사흘 뒤에 대설 경보래! 주문해서 일주일 걸리면 늦어.', clue: '대설 경보 D-3 · 납기가 핵심' },
    { k: 'jacheong', n: '보건진료소 간호사', line: '비싸도 바로 투입할 수 있는 제설차가 있다던데요?', clue: '재고 보유 제품 확인' } ],
  thanks: '길이 열려서 병원도 갈 수 있어요!' },

{ id: 'chungbuk', name: '충북', full: '충청북도', town: '미호강 저지대 마을', mission: '집중호우 대비 침수 방지', item: '배수펌프', icon: '💧',
  lat: 36.8, lon: 127.75, color: '#3f86b0', land: '#a6bf9a', sky: ['#dfe7ea', '#bccbd2'], wx: 'rain', weather: '☂ 호우 주의 · 19°',
  problem: '빗물이 고이는 저지대', fixed: '배수펌프 가동', before: '비만 오면 마을 안길에 물이 차올라요.', after: '배수펌프가 빗물을 강으로 퍼내 길이 말랐어요.',
  budget: 80, focus: 'safety', second: 'upkeep', perf: '배수 용량', min: 80,
  pt: { safety: '침수를 막는 배수 용량에 집중해요.', comfort: '대피소 담요·물품도 함께 사요.', upkeep: '펌프 점검·연료비를 남겨요.' },
  event: { name: '집중호우', icon: '⛈', d: 4, hit: '시간당 60mm 집중호우가 쏟아져요!' },
  products: [['소형 수중펌프', 24, 60, 3, 1, '가정용 · 용량 작음'], ['이동식 대용량 배수펌프', 42, 86, 2, 3, '트럭 견인 · 빠른 설치'], ['고정식 자동 배수펌프장', 66, 98, 2, 15, '건물 공사 필요']],
  residents: [
    { k: 'jacheong', n: '저지대 농민', line: '작은 펌프는 금방 넘쳐요. 배수 용량 80은 돼야 해요.', clue: '성능 80 이상 · 안전 최우선' },
    { k: 'mongdol', n: '마을 청년회장', line: '나흘 뒤 집중호우 예보예요. 공사가 오래 걸리는 건 안 돼요.', clue: '집중호우 D-4' },
    { k: 'chief', n: '마을 이장', line: '펌프도 기름 먹고 점검해야 돌아가. 관리비도 생각해 둬.', clue: '유지관리 고려' } ],
  thanks: '비가 와도 길에 물이 안 차요!' },

{ id: 'chungnam', name: '충남', full: '충청남도', town: '내포 들녘 마을', mission: '농촌 급수시설 복구', item: '급수관·펌프', icon: '🚰',
  lat: 36.6, lon: 126.72, color: '#4e9bb5', land: '#cdb98b', sky: ['#f3ecd8', '#e1d6b6'], wx: 'dry', weather: '☀ 가뭄 · 강수 0mm',
  problem: '물이 끊긴 논밭', fixed: '물길이 흐르는 들녘', before: '낡은 급수관이 터져 논이 말라가고 있어요.', after: '새 급수관을 따라 물이 흐르고 모가 파랗게 자랐어요.',
  budget: 70, focus: 'upkeep', second: 'safety', perf: '급수 성능', min: 70,
  pt: { safety: '누수·감전 위험부터 막는 데 집중해요.', comfort: '농민 쉼터와 세척대도 함께 만들어요.', upkeep: '관이 또 터지지 않게 관리 예산을 남겨요.' },
  event: { name: '모내기철 가뭄', icon: '🌾', d: 8, hit: '모내기철인데 비가 오지 않아요!' },
  products: [['PVC 급수관+소형펌프', 22, 67, 6, 3, '저렴 · 자주 파손'], ['내구성 PE관+인버터 펌프', 38, 84, 2, 6, '튼튼 · 전기 절약'], ['원격관리 스마트 급수', 54, 93, 1, 10, '휴대폰 원격 제어']],
  residents: [
    { k: 'chief', n: '들녘 이장', line: '관이 해마다 터져. 이번엔 고친 뒤 관리할 예산까지 꼭 남겨둬야 해.', clue: '유지관리 예산 확보 우선' },
    { k: 'jacheong', n: '청년 농부', line: '물이 논 끝까지 가려면 급수 성능 70은 넘어야 해요.', clue: '성능 70 이상' },
    { k: 'mongdol', n: '방앗간 주인', line: '여드레 뒤면 모내기예요. 그 전에 물이 와야 해요.', clue: '모내기 D-8' } ],
  thanks: '논에 물이 차니 마음까지 시원해요!' },

{ id: 'jeonbuk', name: '전북', full: '전북특별자치도', town: '만경 들녘 작목반', mission: '농산물 신선도 유지', item: '저온저장 설비', icon: '🥬',
  lat: 35.72, lon: 127.12, color: '#6aa84f', land: '#b5c98e', sky: ['#f2f2dc', '#dfe3bd'], wx: 'heat', weather: '☀ 무더위 · 33°',
  problem: '햇볕에 시드는 수확물', fixed: '저온저장고 가동', before: '수확한 채소가 땡볕에서 시들어 가요.', after: '저온저장고에 채소가 싱싱하게 보관되고 출하 트럭이 떠나요.',
  budget: 80, focus: 'upkeep', second: 'comfort', perf: '보관 성능', min: 75,
  pt: { safety: '전기 안전·화재 예방 설비에 집중해요.', comfort: '선별 작업장 그늘막을 함께 만들어요.', upkeep: '전기료·냉매 점검비를 넉넉히 남겨요.' },
  event: { name: '수확기 무더위', icon: '🥵', d: 6, hit: '수확기에 33도 무더위가 찾아왔어요!' },
  products: [['중고 냉장 컨테이너', 26, 70, 6, 2, '온도 불안정 · 전기료 높음'], ['고효율 저온저장고', 46, 85, 2, 5, '단열 패널 · 전기 절약'], ['스마트 CA 저장고', 64, 96, 2, 12, '공기 조절 · 장기 보관']],
  residents: [
    { k: 'jacheong', n: '작목반장', line: '냉장고는 사는 것보다 돌리는 게 더 비싸요. 전기료·점검비를 꼭 남겨야 해요.', clue: '유지관리 예산 확보 우선' },
    { k: 'chief', n: '배추 농가 어르신', line: '온도가 들쭉날쭉하면 다 물러. 보관 성능 75 이상이어야 해.', clue: '성능 75 이상' },
    { k: 'mongdol', n: '출하 트럭 기사', line: '엿새 뒤부터 본격 수확이에요. 그 전에 저장고가 있어야 해요.', clue: '수확기 D-6' } ],
  thanks: '채소가 싱싱하니 제값 받고 팔아요!' },

{ id: 'jeonnam', name: '전남', full: '전라남도', town: '다도해 작은 섬마을', mission: '섬마을 식수 공급 개선', item: '정수설비', icon: '🚱',
  lat: 34.62, lon: 126.6, color: '#3aa0a8', land: '#d8cc9e', sky: ['#e0f1f2', '#bfe0e2'], wx: 'dry', weather: '☀ 가뭄 · 급수선 감편',
  problem: '먹을 물이 부족한 섬', fixed: '깨끗한 물이 나오는 정수장', before: '급수선이 줄어 물통에 물을 받으려 줄을 서요.', after: '정수설비가 바닷물을 마실 물로 바꿔 수도꼭지에서 물이 나와요.',
  budget: 80, focus: 'safety', second: 'upkeep', perf: '정수 성능', min: 80,
  pt: { safety: '안전한 식수 수질에 예산을 집중해요.', comfort: '공동 빨래터·쉼터를 함께 만들어요.', upkeep: '필터 교체비를 남겨둬요.' },
  event: { name: '급수선 운항 중단', icon: '⛴', d: 4, hit: '풍랑으로 급수선이 끊겼어요! 물이 바닥나요.' },
  products: [['가정용 정수기 묶음', 20, 62, 4, 2, '빗물·지하수만 처리'], ['소형 마을 정수설비', 46, 86, 3, 7, '해수 담수화 · 주문 제작'], ['컨테이너형 정수 플랜트', 62, 94, 2, 4, '완제품 · 배로 바로 운송']],
  residents: [
    { k: 'sora', n: '섬마을 노인회장', line: '바닷물을 거르려면 정수 성능 80은 넘어야 하네. 가정용으론 어림없어.', clue: '성능 80 이상 · 식수 안전' },
    { k: 'jacheong', n: '분교 선생님', line: '나흘 뒤 풍랑 예보예요. 급수선이 끊기기 전에 설치돼야 해요!', clue: '풍랑 D-4 · 납기 중요' },
    { k: 'chief', n: '선착장 이장', line: '필터는 주기적으로 갈아야 한다던데, 관리비도 잊지 마.', clue: '필터 교체비' } ],
  thanks: '수도꼭지에서 깨끗한 물이 나와요!' },

{ id: 'gyeongbuk', name: '경북', full: '경상북도', town: '안동 하회 들마을', mission: '농촌 응급 대응 강화', item: '자동심장충격기·안내표지', icon: '❤',
  lat: 36.4, lon: 128.75, color: '#d8545e', land: '#b9c79a', sky: ['#f3efe2', '#e2dbc5'], wx: 'clear', weather: '⛅ 맑음 · 22°',
  problem: '응급 장비 없는 마을회관', fixed: 'AED와 안내표지 설치', before: '어르신이 쓰러졌는데 응급 장비가 어디 있는지 몰라요.', after: '안내표지를 따라 AED를 찾아 빠르게 응급처치를 했어요.',
  budget: 50, focus: 'safety', second: 'comfort', perf: '응급 대응 성능', min: 75,
  pt: { safety: '응급장비와 안내표지에 집중해요.', comfort: '마을회관 쉼터 정비도 함께 해요.', upkeep: '배터리·패드 교체비를 남겨요.' },
  event: { name: '마을 경로잔치', icon: '🎉', d: 6, hit: '경로잔치에 어르신 100명이 모였어요!' },
  products: [['보급형 AED', 16, 70, 2, 2, '본체만 · 표지 없음'], ['AED+보관함+안내표지', 26, 85, 2, 4, '경보 보관함 · 길 안내판 6개'], ['원격관리 AED 시스템', 38, 95, 3, 8, '원격 점검 · 119 연동']],
  residents: [
    { k: 'chiefLying', n: '쓰러진 이장님', line: '(가슴을 움켜쥐며) 으윽… 숨이…', clue: '골든타임 4분 · 안전 최우선', lying: true },
    { k: 'sorang', n: '마을 보건 도우미', line: '장비만 있으면 안 돼요. 어디 있는지 찾을 수 있게 안내표지까지(성능 75 이상) 필요해요!', clue: '성능 75 이상 · 안내표지 포함' },
    { k: 'mongdol', n: '부녀회장', line: '엿새 뒤 경로잔치에 어르신들이 많이 오세요. 그 전에 꼭 있어야 해요.', clue: '경로잔치 D-6' } ],
  thanks: '덕분에 이장님이 무사하세요. 고마워요!' },

{ id: 'gyeongnam', name: '경남', full: '경상남도', town: '진해 벚꽃 마을회관', mission: '이동약자를 위한 시설 개선', item: '경사로·편의시설', icon: '♿',
  lat: 35.3, lon: 128.2, color: '#d983a6', land: '#c6c9a4', sky: ['#f8ecf0', '#ead3dc'], wx: 'clear', weather: '🌸 꽃바람 · 19°',
  problem: '계단뿐인 회관 입구', fixed: '누구나 오르는 경사로', before: '휠체어와 유모차는 계단 앞에서 멈춰야 해요.', after: '완만한 경사로와 손잡이로 누구나 회관에 들어가요.',
  budget: 70, focus: 'comfort', second: 'safety', perf: '접근성', min: 75,
  pt: { safety: '미끄럼·추락 방지 난간에 집중해요.', comfort: '경사로와 함께 쉼터·화장실 손잡이도 갖춰요.', upkeep: '보수·청소비를 남겨둬요.' },
  event: { name: '벚꽃 축제', icon: '🌸', d: 9, hit: '벚꽃 축제에 방문객이 몰려와요!' },
  products: [['이동식 임시 경사로', 14, 66, 3, 1, '가파름 · 손잡이 없음'], ['고정식 경사로+손잡이+점자블록', 36, 84, 2, 6, '완만한 기울기 · 양쪽 손잡이'], ['경사로+자동문+승강 리프트', 60, 97, 4, 14, '공사 김 · 전기료']],
  residents: [
    { k: 'chief', n: '휠체어 타는 어르신', line: '회관에 가고 싶어도 계단 때문에 못 가. 누구나 편히 드나들 수 있게 해줘.', clue: '이동 편의시설 우선' },
    { k: 'jacheong', n: '유모차 끄는 이웃', line: '임시 경사로는 너무 가팔라요. 접근성 75 이상은 돼야 해요.', clue: '성능 75 이상' },
    { k: 'sora', n: '축제 위원장', line: '아흐레 뒤 벚꽃 축제요. 그 전에 완성되면 좋겠소.', clue: '벚꽃 축제 D-9' } ],
  thanks: '이제 혼자서도 회관에 갈 수 있어요!' },

{ id: 'jeju', name: '제주', full: '제주특별자치도', town: '돌담길 귤밭 마을', mission: '태풍 시 비상전력 확보', item: '태양광·비상배터리', icon: '🔋',
  lat: 33.38, lon: 126.55, color: '#f08a3c', land: '#a8bf8c', sky: ['#e3edf0', '#c3d3da'], wx: 'wind', weather: '🌀 태풍 북상 중',
  problem: '정전에 취약한 마을회관', fixed: '태양광+비상배터리 대기', before: '태풍이 오면 정전이 돼 대피소가 깜깜해져요.', after: '지붕 태양광이 배터리를 채워 정전에도 불이 켜져요.',
  budget: 90, focus: 'safety', second: 'upkeep', perf: '비상전력 성능', min: 80,
  pt: { safety: '정전 대비 전력 확보에 집중해요.', comfort: '대피소 담요·간이침대를 함께 사요.', upkeep: '배터리 점검비를 남겨둬요.' },
  event: { name: '태풍 북상', icon: '🌀', d: 4, hit: '태풍이 상륙했어요! 마을 전체가 정전됐어요.' },
  products: [['휴대용 발전기', 22, 70, 7, 1, '연료 필요 · 소음'], ['태양광+ESS 표준형', 54, 88, 2, 6, '주문 설치'], ['태양광+ESS 신속 패키지', 72, 95, 2, 3, '사전 조립 · 빠른 설치']],
  residents: [
    { k: 'sora', n: '해녀회 대장', line: '정전되면 대피소에서 밤을 새워야 하오. 비상전력 성능 80은 필요하오.', clue: '성능 80 이상 · 안전 최우선' },
    { k: 'jacheong', n: '귤밭 농부', line: '나흘 뒤에 태풍이 올라온대요! 엿새씩 걸리면 늦어요.', clue: '태풍 D-4 · 납기 중요' },
    { k: 'mongdol', n: '돌담 지킴이', line: '발전기는 기름값이 계속 들어. 오래 쓸 걸로 골라줘.', clue: '연료비(유지비) 주의' } ],
  thanks: '태풍에도 대피소 불이 꺼지지 않았어요!' }
];

// 추천 여행 순서 (수도권 → 강원 → 충청 → 호남 → 제주 → 영남)
const ROUTE = ['seoul', 'gyeonggi', 'incheon', 'gangwon', 'chungbuk', 'sejong', 'daejeon', 'chungnam', 'jeonbuk', 'gwangju', 'jeonnam', 'jeju', 'gyeongnam', 'busan', 'ulsan', 'daegu', 'gyeongbuk'];

const SCORE_PARTS = [['sat', '주민 만족도', 30], ['bud', '예산 운영', 20], ['fit', '제품 적합성', 25], ['time', '납기·위기 대응', 15], ['care', '유지관리 효율', 10]];

function capOf(reg, pri) { return Math.floor(reg.budget * PRI[pri].cap) }
function expressOf(reg) { return { cost: Math.round(reg.budget * .12), days: 3 } }

// 점수 계산: ch = { heard: 들은 주민 수, pri, prod: 0~2, express }
function scoreRegion(reg, ch) {
  const [, price, perf, maint, days] = reg.products[ch.prod];
  const ex = expressOf(reg), spent = price + (ch.express ? ex.cost : 0);
  const eff = days - (ch.express ? ex.days : 0), meets = perf >= reg.min, late = eff > reg.event.d;
  const survey = [0, 4, 7, 10][Math.min(3, ch.heard)];
  const priPts = ch.pri === reg.focus ? 12 : ch.pri === reg.second ? 7 : 3;
  const sat = survey + priPts + (meets ? 8 : 2) - (late ? 3 : 0);
  const r = spent / reg.budget;
  const bud = r <= .5 ? 20 : r <= .65 ? 17 : r <= .8 ? 13 : 9;
  const fit = meets ? 17 + Math.round(8 * Math.min(1, (perf - reg.min) / 25)) : Math.round(12 * perf / reg.min);
  const time = late ? Math.max(3, 15 - 3 * (eff - reg.event.d)) : 15;
  const minMaint = Math.min(...reg.products.map(p => p[3]));
  const care = Math.min(10, Math.round(10 * minMaint / maint) + (ch.pri === 'upkeep' ? 3 : 0));
  const parts = { sat: Math.max(0, sat), bud, fit, time, care };
  const total = Object.values(parts).reduce((a, b) => a + b, 0);
  return { parts, total, stars: total >= 85 ? 3 : total >= 65 ? 2 : 1, meets, late, spent, eff, price, perf, maint, days };
}

if (typeof module !== 'undefined') module.exports = { REGIONS, PRI, ROUTE, scoreRegion, capOf, expressOf };
