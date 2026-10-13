// AIチーム接続用。{status:'detected'|'undetected'|'unavailable', message:string} を返す。
// カメラが動いていることを「姿勢検出成功」として扱わない。
export async function inspectPose(video){return {status:'unavailable',message:'姿勢検出は未接続（カメラ動作確認のみ）'};}
