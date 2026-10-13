export class Camera {
  constructor(video){this.video=video;this.stream=null;}
  async start(){this.stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});this.video.srcObject=this.stream;await this.video.play();}
  available(){return this.video.readyState>=2 && this.video.videoWidth>0 && this.stream?.getVideoTracks().some(t=>t.readyState==='live');}
  async capture(){if(!this.available())throw Error('カメラ映像がありません');const c=document.createElement('canvas');c.width=this.video.videoWidth;c.height=this.video.videoHeight;c.getContext('2d').drawImage(this.video,0,0);return new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(Error('写真取得に失敗しました')),'image/jpeg',0.85));}
  stop(){this.stream?.getTracks().forEach(t=>t.stop());}
}
