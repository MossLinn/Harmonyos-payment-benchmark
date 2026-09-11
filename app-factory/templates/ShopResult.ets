// 订单结果页模板（ShopResult）—— 页 5/5
// 槽位：APP_NAME / TASK_ID
import { router } from '@kit.ArkUI';

@Entry
@Component
struct Result {
  @StorageLink('pay_result') payResult: string = ''
  @StorageLink('order_no') orderNo: string = ''
  @StorageLink('order_contact') orderContact: string = ''

  build() {
    Column({ space: 14 }) {
      if (this.payResult === 'success') {
        Text('🎉').fontSize(52)
        Text('订单支付成功').fontSize(19).fontWeight(FontWeight.Bold).id('order_done_marker')
        Text('商家将尽快为你发货').fontSize(13).fontColor('#666666')
        Text(`收货人：${this.orderContact}`).fontSize(12).fontColor('#666666').id('result_contact')
        Text('订单编号：' + this.orderNo).fontSize(12).fontColor('#999999')
        Button('返回首页').width('70%').height(46)
          .id('back_home')
          .onClick(() => {
            router.clear()
            router.pushUrl({ url: 'pages/Index' })
          })
      } else {
        Text('⏳').fontSize(52)
        Text('订单待支付').fontSize(17)
        Text('订单编号：' + this.orderNo).fontSize(12).fontColor('#999999')
        Button('返回首页').width('70%').height(46)
          .onClick(() => {
            router.clear()
            router.pushUrl({ url: 'pages/Index' })
          })
      }
      Text('{{APP_NAME}} · {{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
    }
    .width('100%').height('100%').justifyContent(FlexAlign.Center)
    .backgroundColor('#F5F6F8')
  }
}