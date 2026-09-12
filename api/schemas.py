"""Schemas públicos do contrato /api/v1."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=1024)


class UserResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    status: str
    must_change_password: bool = False


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    request_id: str


class AboutResponse(BaseModel):
    name: str
    full_name: str
    version: str
    architecture: str


class RaceResponse(BaseModel):
    id: int
    name: str
    date: str
    time: str | None = None
    type: str
    status: str
    season: str
    circuit_id: str | None = None


class TelemetryWeather(BaseModel):
    available: bool
    reason: str | None = None
    forecast_at: str | None = None
    condition: str | None = None
    icon: str | None = None
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    precipitation_probability: int | None = None
    wind_speed_kmh: float | None = None


class TelemetryNextRace(BaseModel):
    id: int
    name: str
    round: int
    date: str
    time: str
    starts_at: str
    type: str
    circuit_id: str | None = None
    weather: TelemetryWeather | None = None


class TelemetryMetrics(BaseModel):
    current_position: int | None = None
    points: float
    bets_submitted: int
    races_total: int


class TelemetryEvolutionPoint(BaseModel):
    race_id: int
    race_name: str
    position: int | None = None
    points: float
    cumulative_points: float


class TelemetryRankingEntry(BaseModel):
    position: int
    name: str
    points: float
    is_current_user: bool


class TelemetryResponse(BaseModel):
    user_name: str
    season: str
    next_race: TelemetryNextRace | None = None
    metrics: TelemetryMetrics
    evolution: list[TelemetryEvolutionPoint]
    ranking: list[TelemetryRankingEntry]


class ClassificationEntry(BaseModel):
    position: int
    participant: str
    total: float
    champion_bonus: float
    vice_bonus: float
    team_bonus: float
    discard: float
    valid_total: float
    difference: float
    movement: int | None = None
    eleventh_hits: int
    championship_hits: int


class ClassificationRaceScore(BaseModel):
    participant: str
    points: float
    maximum_percentage: float
    cumulative_points: float
    position: int


class ClassificationRace(BaseModel):
    race_id: int
    race_name: str
    race_type: str
    maximum_points: float
    scores: list[ClassificationRaceScore]


class ClassificationResponse(BaseModel):
    season: str
    discard_active: bool
    entries: list[ClassificationEntry]
    races: list[ClassificationRace] = []


class RaceBetDriver(BaseModel):
    name: str
    team: str


class RaceBetOption(BaseModel):
    id: int
    name: str
    type: str
    date: str
    time: str
    is_open: bool
    deadline: str | None = None
    deadline_message: str


class RaceBetRules(BaseModel):
    total_chips: int
    max_chips_per_driver: int
    minimum_drivers: int
    same_team_allowed: bool


class RaceBetAllocation(BaseModel):
    driver: str = Field(min_length=1, max_length=120)
    chips: int = Field(ge=1, le=100)


class RaceBetCurrent(BaseModel):
    allocations: list[RaceBetAllocation]
    eleventh_driver: str
    submitted_at: str | None = None


class RaceBetSnapshot(BaseModel):
    season: str
    races: list[RaceBetOption]
    selected_race: RaceBetOption | None = None
    drivers: list[RaceBetDriver]
    rules: RaceBetRules
    current_bet: RaceBetCurrent | None = None


class RaceBetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    race_id: int = Field(gt=0)
    allocations: list[RaceBetAllocation] = Field(min_length=1, max_length=20)
    eleventh_driver: str = Field(min_length=1, max_length=120)


class RaceBetResponse(BaseModel):
    status: str
    race_id: int
    message: str


class DriverBetAggregate(BaseModel):
    driver: str
    team: str | None = None
    bets: int
    chips: int = 0


class AnalysisParticipant(BaseModel):
    id: int
    name: str


class BetsAnalysisResponse(BaseModel):
    season: str
    scope: str
    bet_count: int
    race_count: int
    result_count: int
    by_driver: list[DriverBetAggregate]
    eleventh: list[DriverBetAggregate]
    participants: list[AnalysisParticipant] = []
    selected_participant_id: int | None = None


class HallEntry(BaseModel):
    season: str
    position: int
    points: float
    participant: str


class HallWinner(BaseModel):
    participant: str
    wins: int


class HallSeasonStat(BaseModel):
    season: str
    participants: int
    best_points: float | None = None
    average_points: float | None = None
    champion: HallEntry | None = None


class HallPositionCount(BaseModel):
    position: int
    count: int


class HallDistribution(BaseModel):
    participant: str
    positions: list[HallPositionCount]


class HallOfFameResponse(BaseModel):
    source: str
    seasons: list[str]
    entries: list[HallEntry]
    top_winners: list[HallWinner]
    season_stats: list[HallSeasonStat]
    distribution: list[HallDistribution]


class AdminParticipant(BaseModel):
    id: int
    name: str


class HallAdminWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    season: str = Field(pattern=r"^\d{4}$")
    position: int = Field(ge=1, le=1000)
    points: float = Field(ge=0)


class HallAdminUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season: str = Field(pattern=r"^\d{4}$")
    position: int = Field(ge=1, le=1000)
    points: float = Field(ge=0)


class HallAdminRecord(BaseModel):
    id: int
    user_id: int
    participant: str
    season: str
    position: int
    points: float


class HallAdminResponse(BaseModel):
    records: list[HallAdminRecord]
    participants: list[AdminParticipant]

class FinancialPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    paid: bool

class FinancialWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season: str = Field(pattern=r"^\d{4}$")
    fee: float = Field(ge=0)
    payments: list[FinancialPayment] = Field(default_factory=list, max_length=500)

class FinancialParticipant(BaseModel):
    user_id: int
    name: str
    email: str
    paid: bool

class FinancialSummary(BaseModel):
    participants_total: int
    paid_total: int
    pending_total: int
    collected: float
    outstanding: float
    total_due: float

class FinancialPrizes(BaseModel):
    winner: float
    runner_up: float
    third: float
    administration: float

class FinancialResponse(BaseModel):
    season: str
    fee: float
    participants: list[FinancialParticipant]
    summary: FinancialSummary
    prizes: FinancialPrizes

class FinancialReminderResponse(BaseModel):
    status: str
    recipients: int

class RuleWriteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    nome_regra: str = Field(min_length=1, max_length=120)
    quantidade_fichas: int = Field(ge=1, le=100)
    fichas_por_piloto: int = Field(ge=1, le=100)
    mesma_equipe: bool = False
    descarte: bool = False
    pontos_pole: int = Field(ge=0, le=1000)
    pontos_vr: int = Field(ge=0, le=1000)
    pontos_posicoes: list[int] = Field(min_length=1, max_length=20)
    pontos_11_colocado: int = Field(ge=0, le=1000)
    regra_sprint: bool = False
    pontos_sprint_pole: int = Field(ge=0, le=1000)
    pontos_sprint_vr: int = Field(ge=0, le=1000)
    pontos_sprint_posicoes: list[int] = Field(min_length=1, max_length=20)
    pontos_dobrada: bool = False
    bonus_vencedor: int = Field(ge=0, le=1000)
    bonus_podio_completo: int = Field(ge=0, le=1000)
    bonus_podio_qualquer: int = Field(ge=0, le=1000)
    qtd_minima_pilotos: int = Field(ge=1, le=20)
    penalidade_abandono: bool = False
    pontos_penalidade: int = Field(ge=0, le=1000)
    penalidade_auto_percent: int = Field(ge=0, le=100)
    pontos_campeao: int = Field(ge=0, le=2000)
    pontos_vice: int = Field(ge=0, le=2000)
    pontos_equipe: int = Field(ge=0, le=2000)

class RuleAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season: str = Field(pattern=r"^\d{4}$")
    rule_id: int = Field(gt=0)

class RuleCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class BettingLogItem(BaseModel):
    id: int
    usuario_id: int | None = None
    data: str | None = None
    horario: str | None = None
    apostador: str | None = None
    nome_prova: str | None = None
    pilotos: str | None = None
    aposta: str | None = None
    piloto_11: str | None = None
    tipo_aposta: int | None = None
    automatica: int | None = None
    ip_address: str | None = None
    temporada: str | int | None = None
    status: str | None = None


class BettingLogsResponse(BaseModel):
    season: str
    scope: str
    pagination: PaginationResponse
    items: list[BettingLogItem]


class AccessLogItem(BaseModel):
    id: int
    created_at: str
    evento: str | None = None
    sucesso: bool | None = None
    user_id: int | None = None
    email: str | None = None
    nome: str | None = None
    perfil: str | None = None
    ip_address: str | None = None
    detalhes: str | None = None


class AccessLogsResponse(BaseModel):
    pagination: PaginationResponse
    successes: int
    failures: int
    items: list[AccessLogItem]


class F1DriverStanding(BaseModel):
    position: int
    driver: str
    points: float
    wins: int
    nationality: str
    constructor: str


class F1ConstructorStanding(BaseModel):
    position: int
    constructor: str
    points: float
    wins: int
    nationality: str


class F1ProgressionPoint(BaseModel):
    round: int
    race: str
    points: dict[str, float]


class F1QualifyingDelta(BaseModel):
    driver: str
    qualifying: int
    race: int
    delta: int


class F1FastestLap(BaseModel):
    driver: str
    time: str


class F1PitStop(BaseModel):
    driver: str
    lap: int
    stop: int
    time: str


class F1DashboardResponse(BaseModel):
    season: str
    driver_standings: list[F1DriverStanding]
    constructor_standings: list[F1ConstructorStanding]
    progression_drivers: list[str]
    progression: list[F1ProgressionPoint]
    qualifying_vs_race: list[F1QualifyingDelta]
    fastest_laps: list[F1FastestLap]
    pit_stops: list[F1PitStop]
    average_stops: float | None = None


class ChampionshipBetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    champion: str = Field(min_length=1, max_length=120)
    vice: str = Field(min_length=1, max_length=120)
    team: str = Field(min_length=1, max_length=120)


class ChampionshipBetRecord(BaseModel):
    user_nome: str | None = None
    champion: str
    vice: str
    team: str
    season: str | int
    bet_time: str | None = None


class ChampionshipResult(BaseModel):
    season: str
    champion: str
    vice: str
    team: str


class ChampionshipResponse(BaseModel):
    season: str
    drivers: list[str]
    teams: list[str]
    current_bet: ChampionshipBetRecord | None = None
    history: list[ChampionshipBetRecord]
    all_bets: list[ChampionshipBetRecord]
    official_result: ChampionshipResult | None = None
    can_bet: bool
    deadline_message: str
    deadline: str | None = None
