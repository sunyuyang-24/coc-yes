"use client";

import { useState, useCallback } from "react";
import { apiRequest, apiUrl } from "@/lib/api";

export type RuleSearchResult = {
  file: string;
  page: number;
  excerpt: string;
};

export type RuleSearchResponse = {
  keyword: string;
  total: number;
  results: RuleSearchResult[];
};

export type IndexStatus = {
  ready: boolean;
  source_file?: string;
  total_pages?: number;
  indexed_pages?: number;
  pdf_exists?: boolean;
};

type Props = {
  onSendToChat?: (text: string) => void;
  showSendToChat?: boolean;
};

export function RulesSearchPanel({ onSendToChat, showSendToChat }: Props) {
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<RuleSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [indexReady, setIndexReady] = useState<boolean | null>(null);
  const [notice, setNotice] = useState("");

  const checkIndex = useCallback(async () => {
    try {
      const status = await apiRequest<IndexStatus>("/api/rules/index-status");
      setIndexReady(status.ready);
      if (!status.ready && status.pdf_exists) {
        setNotice("规则书索引尚未构建，首次搜索时自动构建（约需数秒）。");
      } else if (!status.pdf_exists) {
        setNotice("未找到规则书 PDF，请放入 COC7th核心规则书原文.pdf。");
      } else {
        setNotice("");
      }
    } catch {
      setNotice("无法连接后端服务。");
    }
  }, []);

  const search = useCallback(
    async (searchKeyword?: string) => {
      const kw = (searchKeyword ?? keyword).trim();
      if (!kw) return;

      setLoading(true);
      setNotice("正在搜索...");
      try {
        const resp = await apiRequest<RuleSearchResponse>("/api/rules/search", {
          method: "POST",
          body: JSON.stringify({ keyword: kw, limit: 15 }),
        });
        setResults(resp.results);
        setTotal(resp.total);
        setSearched(true);
        setIndexReady(true);
        if (resp.total === 0) {
          setNotice(`未找到与"${kw}"相关的结果，请尝试其他关键词。`);
        } else {
          setNotice(`找到 ${resp.total} 条与"${kw}"相关的结果。`);
        }
      } catch (err) {
        setNotice(`搜索失败: ${err instanceof Error ? err.message : "未知错误"}`);
      } finally {
        setLoading(false);
      }
    },
    [keyword]
  );

  const handleSendToChat = (result: RuleSearchResult) => {
    const text = `[规则引用] ${result.file} 第${result.page}页: "${result.excerpt}"`;
    onSendToChat?.(text);
  };

  return (
    <div className="rules-panel">
      <div className="rules-panel__header">
        <h3>规则书检索</h3>
        <button
          className="text-button"
          onClick={checkIndex}
          type="button"
          title="检查索引状态"
        >
          索引状态
        </button>
      </div>

      {indexReady === false && (
        <p className="notice">规则书索引未就绪，首次搜索会自动构建。</p>
      )}

      <form
        className="rules-search-form"
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <input
          className="rules-search-form__input"
          placeholder="输入规则关键词，如 sanity、攻击、san值..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <button
          className="button button--primary"
          disabled={loading || !keyword.trim()}
          type="submit"
        >
          {loading ? "搜索中..." : "搜索"}
        </button>
      </form>

      {notice && <p className="notice">{notice}</p>}

      {searched && results.length > 0 && (
        <ul className="rules-results">
          {results.map((result, i) => (
            <li key={`${result.page}-${i}`} className="rules-result">
              <div className="rules-result__meta">
                <span className="rules-result__source">
                  {result.file}
                </span>
                <span className="rules-result__page">
                  第 {result.page} 页
                </span>
              </div>
              <p className="rules-result__excerpt">{result.excerpt}</p>
              {showSendToChat && (
                <button
                  className="text-button"
                  onClick={() => handleSendToChat(result)}
                  type="button"
                >
                  发送至聊天
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {searched && results.length === 0 && !loading && (
        <p className="notice">未找到相关结果。请尝试其他关键词或确认规则书 PDF 已就绪。</p>
      )}
    </div>
  );
}