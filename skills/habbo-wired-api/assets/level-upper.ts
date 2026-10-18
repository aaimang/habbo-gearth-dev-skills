// Official Level Up add-on snippet (shared by the WIRED team), with the
// LinearLevelUpper#maxXp fix applied. Python port: ../scripts/level_upper.py

export interface LevelUpperConfig {
  currentLevel(xp: bigint): bigint;
  totalXpRequired(xp: bigint): bigint;
  progress(xp: bigint): bigint;
  progressPercentage(xp: bigint): bigint;
  xpRemaining(xp: bigint): bigint;
  isMaxed(xp: bigint): boolean;
  maxLevel(): bigint;
  maxXp(): bigint;
  boundedValue(xp: bigint): bigint;
}

abstract class BaseLevelUpper implements LevelUpperConfig {
  public boundedValue(xp: bigint): bigint {
    if (xp < 0n) {
      return 0n;
    }
    const maxXp = this.maxXp();
    return xp > maxXp ? maxXp : xp;
  }

  public abstract currentLevel(xp: bigint): bigint;
  public abstract totalXpRequired(xp: bigint): bigint;
  public abstract progress(xp: bigint): bigint;
  public abstract progressPercentage(xp: bigint): bigint;
  public abstract xpRemaining(xp: bigint): bigint;
  public abstract isMaxed(xp: bigint): boolean;
  public abstract maxLevel(): bigint;
  public abstract maxXp(): bigint;
}

class LinearLevelUpper extends BaseLevelUpper {
  public constructor(
    private readonly stepSize: bigint,
    private readonly maximumLevel: bigint
  ) {
    super();
  }

  public currentLevel(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    return minBigInt(this.maximumLevel, 1n + bounded / this.stepSize);
  }

  public totalXpRequired(xp: bigint): bigint {
    return this.isMaxed(xp) ? 0n : this.stepSize;
  }

  public progress(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    return this.isMaxed(xp) ? 0n : bounded % this.stepSize;
  }

  public progressPercentage(xp: bigint): bigint {
    if (this.isMaxed(xp)) {
      return 0n;
    }
    return BigInt(Math.floor((Number(this.progress(xp)) / Number(this.stepSize)) * 100));
  }

  public xpRemaining(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    return this.isMaxed(bounded) ? 0n : this.stepSize - (bounded % this.stepSize);
  }

  public isMaxed(xp: bigint): boolean {
    return this.currentLevel(xp) >= this.maximumLevel;
  }

  public maxLevel(): bigint {
    return this.maximumLevel;
  }

  public maxXp(): bigint {
    // Fixed: the original snippet returned maximumLevel * stepSize. The server
    // was corrected to (maximumLevel - 1) * stepSize; level 1 starts at 0 XP.
    return (this.maximumLevel - 1n) * this.stepSize;
  }
}

class InterpolateLevelUpper extends BaseLevelUpper {
  private readonly xpToLevel: Array<{ xp: bigint; level: bigint }>;

  public constructor(levelToXpMap: Readonly<Record<number, bigint>>) {
    super();
    this.xpToLevel = Object.entries(levelToXpMap)
      .map(([level, xp]) => ({ level: BigInt(level), xp }))
      .sort((left, right) => (left.xp < right.xp ? -1 : left.xp > right.xp ? 1 : 0));
  }

  public currentLevel(xp: bigint): bigint {
    return this.findProgressInfo(xp).currentLevel;
  }

  public totalXpRequired(xp: bigint): bigint {
    const info = this.findProgressInfo(xp);
    return info.nextLevelXp - info.currentLevelXp;
  }

  public progress(xp: bigint): bigint {
    const info = this.findProgressInfo(xp);
    return info.currentXp - info.currentLevelXp;
  }

  public progressPercentage(xp: bigint): bigint {
    const info = this.findProgressInfo(xp);
    const totalRequired = info.nextLevelXp - info.currentLevelXp;
    if (totalRequired === 0n) {
      return 0n;
    }
    return BigInt(Math.floor((Number(info.currentXp - info.currentLevelXp) / Number(totalRequired)) * 100));
  }

  public xpRemaining(xp: bigint): bigint {
    const info = this.findProgressInfo(xp);
    return info.nextLevelXp - info.currentXp;
  }

  public isMaxed(xp: bigint): boolean {
    return this.findProgressInfo(xp).isMaxed;
  }

  public maxLevel(): bigint {
    return this.findProgressInfo(this.maxXp()).currentLevel;
  }

  public maxXp(): bigint {
    if (this.xpToLevel.length === 0) {
      return 0n;
    }
    return this.xpToLevel[this.xpToLevel.length - 1]!.xp;
  }

  private findProgressInfo(xp: bigint): {
    currentLevel: bigint;
    currentLevelXp: bigint;
    currentXp: bigint;
    nextLevelXp: bigint;
    isMaxed: boolean;
  } {
    if (this.xpToLevel.length === 0) {
      return { currentLevel: 1n, currentLevelXp: 0n, currentXp: 0n, nextLevelXp: 0n, isMaxed: true };
    }

    const bounded = this.boundedValue(xp);
    const last = this.xpToLevel[this.xpToLevel.length - 1]!;
    if (bounded >= last.xp) {
      return {
        currentLevel: last.level,
        currentLevelXp: last.xp,
        currentXp: last.xp,
        nextLevelXp: last.xp,
        isMaxed: true
      };
    }

    let floor = { level: 1n, xp: 0n };
    let ceil = this.xpToLevel[0]!;
    for (const entry of this.xpToLevel) {
      if (entry.xp <= bounded) {
        floor = entry;
        continue;
      }
      ceil = entry;
      break;
    }

    const levelDifference = ceil.level - floor.level;
    const xpDifference = ceil.xp - floor.xp;
    const xpPerLevel = Number(xpDifference) / Number(levelDifference);
    const interpolationProgress = Number(bounded - floor.xp);
    let levelSteps = BigInt(
      Math.min(
        Math.max(Math.floor(interpolationProgress / xpPerLevel), 0),
        Number(levelDifference - 1n)
      )
    );

    let currentLevel = floor.level + levelSteps;
    let currentLevelXp = floor.xp + BigInt(Math.floor(xpPerLevel * Number(levelSteps)));
    let nextLevelXp: bigint;

    if (levelSteps === levelDifference - 1n) {
      nextLevelXp = ceil.xp;
    } else {
      nextLevelXp = floor.xp + BigInt(Math.floor(xpPerLevel * Number(levelSteps + 1n)));
      if (bounded >= nextLevelXp) {
        levelSteps += 1n;
        currentLevel = floor.level + levelSteps;
        currentLevelXp = floor.xp + BigInt(Math.floor(xpPerLevel * Number(levelSteps)));
        nextLevelXp = levelSteps === levelDifference ? ceil.xp : floor.xp + BigInt(Math.floor(xpPerLevel * Number(levelSteps + 1n)));
      }
    }

    return {
      currentLevel,
      currentLevelXp,
      currentXp: bounded,
      nextLevelXp,
      isMaxed: false
    };
  }
}

class ExponentialLevelUpper extends BaseLevelUpper {
  private readonly strengthAsDecimal: number;
  private readonly maxXpValue: bigint;

  public constructor(
    private readonly initialXp: bigint,
    strength: bigint,
    private readonly maximumLevel: bigint
  ) {
    super();
    this.strengthAsDecimal = Number(strength) / 100;
    this.maxXpValue = this.xpForLevel(this.maximumLevel);
  }

  public currentLevel(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    if (bounded <= 0n) {
      return 1n;
    }

    const logBase = 1 + this.strengthAsDecimal;
    let level = BigInt(
      Math.floor(
        Math.log((Number(bounded) * this.strengthAsDecimal / Number(this.initialXp)) + 1) / Math.log(logBase)
      ) + 1
    );

    if (level > this.maximumLevel) {
      return this.maximumLevel;
    }
    if (level < 1n) {
      return 1n;
    }
    if (bounded < this.xpForLevel(level)) {
      return level > 1n ? level - 1n : 1n;
    }
    if (bounded >= this.xpForLevel(level + 1n)) {
      return level + 1n > this.maximumLevel ? this.maximumLevel : level + 1n;
    }
    return level;
  }

  public totalXpRequired(xp: bigint): bigint {
    if (this.isMaxed(xp)) {
      return 0n;
    }
    const currentLevel = this.currentLevel(xp);
    return this.xpForLevel(currentLevel + 1n) - this.xpForLevel(currentLevel);
  }

  public progress(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    if (this.isMaxed(bounded)) {
      return 0n;
    }
    const currentLevel = this.currentLevel(bounded);
    return bounded - this.xpForLevel(currentLevel);
  }

  public progressPercentage(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    if (this.isMaxed(bounded)) {
      return 0n;
    }
    const currentLevel = this.currentLevel(bounded);
    const levelXp = this.xpForLevel(currentLevel);
    const nextLevelXp = this.xpForLevel(currentLevel + 1n);
    if (levelXp === nextLevelXp) {
      return 100n;
    }
    return BigInt(Math.floor((Number(bounded - levelXp) / Number(nextLevelXp - levelXp)) * 100));
  }

  public xpRemaining(xp: bigint): bigint {
    const bounded = this.boundedValue(xp);
    if (this.isMaxed(bounded)) {
      return 0n;
    }
    return this.xpForLevel(this.currentLevel(bounded) + 1n) - bounded;
  }

  public isMaxed(xp: bigint): boolean {
    return this.currentLevel(xp) >= this.maximumLevel;
  }

  public maxLevel(): bigint {
    return this.maximumLevel;
  }

  public maxXp(): bigint {
    return this.maxXpValue;
  }

  private xpForLevel(level: bigint): bigint {
    if (level < 1n) {
      return 0n;
    }
    if (level > this.maximumLevel) {
      return this.maxXpValue;
    }
    return BigInt(
      Math.floor(
        Number(this.initialXp) * ((Math.pow(1 + this.strengthAsDecimal, Number(level) - 1) - 1 + 1e-9) / this.strengthAsDecimal)
      )
    );
  }
}

function minBigInt(left: bigint, right: bigint): bigint {
  return left < right ? left : right;
}

export abstract class LevelUpper extends BaseLevelUpper {
  public static linear(stepSize: bigint, maxLevel: bigint): LevelUpperConfig {
    return new LinearLevelUpper(stepSize, maxLevel);
  }

  public static interpolate(levelToXpMap: Readonly<Record<number, bigint>>): LevelUpperConfig {
    return new InterpolateLevelUpper(levelToXpMap);
  }

  public static exponential(initialXp: bigint, strength: bigint, maxLevel: bigint): LevelUpperConfig {
    return new ExponentialLevelUpper(initialXp, strength, maxLevel);
  }
}
