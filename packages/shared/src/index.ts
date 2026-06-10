export type CoreModule = {
  key: string;
  label: string;
  stage: "planned" | "active" | "done";
};

export type RoomMemberRole = "keeper" | "player";

export type RoomMember = {
  id: string;
  displayName: string;
  role: RoomMemberRole;
  joinedAt: string;
  online: boolean;
};

export type DiceBreakdown = {
  kind: "standard" | "coc_d100";
  count: number;
  sides: number;
  rolls: number[];
  modifier: number;
  tensRolls?: number[];
  ones?: number;
  chosenTens?: number;
};

export type DiceRollResult = {
  id: string;
  roomId: string;
  rollerId: string;
  rollerName: string;
  rollerRole: RoomMemberRole;
  expression: string;
  label: string | null;
  total: number;
  breakdown: DiceBreakdown[];
  targetValue: number | null;
  bonusPenalty: number;
  successLevel: "critical" | "extreme" | "hard" | "regular" | "failure" | "fumble" | null;
  successLabel: string | null;
  isSuccess: boolean | null;
  createdAt: string;
};

export type CharacterAttribute = {
  key: string;
  label: string;
  value: number | null;
  half: number | null;
  fifth: number | null;
};

export type CharacterSkill = {
  name: string;
  value: number | null;
  half: number | null;
  fifth: number | null;
};

export type CharacterCard = {
  id: string;
  roomId: string;
  ownerId: string;
  ownerName: string;
  sourceFileName: string;
  basic: Record<string, string>;
  attributes: CharacterAttribute[];
  status: Record<string, number | null>;
  skills: CharacterSkill[];
  weapons: Array<Record<string, string | number | null>>;
  background: Record<string, string>;
  experiences: Array<Record<string, string>>;
  spells: Array<Record<string, string>>;
  warnings: string[];
  keeperNotes: string;
  createdAt: string;
  updatedAt: string;
};

export type ChatMessage = {
  id: string;
  type: "text" | "system" | "dice_roll";
  roomId: string;
  senderId: string | null;
  senderName: string;
  senderRole: RoomMemberRole | "system";
  content: string;
  roll?: DiceRollResult;
  createdAt: string;
};

export type RoomDetail = {
  id: string;
  name: string;
  status: "preparing" | "active" | "ended";
  inviteCode: string;
  createdAt: string;
  members: RoomMember[];
  messages: ChatMessage[];
  rolls?: DiceRollResult[];
  characters?: CharacterCard[];
};

export type BuildPhase = {
  key: string;
  order: number;
  label: string;
  goal: string;
};

export const CORE_MODULES: CoreModule[] = [
  {
    key: "rooms",
    label: "房间",
    stage: "active"
  },
  {
    key: "chat",
    label: "聊天",
    stage: "active"
  },
  {
    key: "dice",
    label: "骰子",
    stage: "active"
  },
  {
    key: "characters",
    label: "角色卡",
    stage: "active"
  },
  {
    key: "rules",
    label: "规则书",
    stage: "planned"
  }
];

export const BUILD_PHASES: BuildPhase[] = [
  {
    key: "foundation",
    order: 0,
    label: "项目骨架",
    goal: "前后端启动、健康检查、工程结构固定。已完成。"
  },
  {
    key: "room-chat",
    order: 1,
    label: "房间与文字聊天",
    goal: "KP 创建房间，玩家进入，同步文字消息。当前正在落地。"
  },
  {
    key: "dice",
    order: 2,
    label: "可信骰子",
    goal: "后端结算投掷，结果进入聊天和日志。当前正在落地。"
  },
  {
    key: "character-card",
    order: 3,
    label: "角色卡解析",
    goal: "上传 Excel 后生成可查看、可投掷的结构化角色卡。当前正在落地。"
  },
  {
    key: "rules-search",
    order: 4,
    label: "规则书检索",
    goal: "本地 PDF 页码级索引，查询结果带来源。"
  }
];
